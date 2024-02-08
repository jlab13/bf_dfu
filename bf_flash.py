#!/usr/bin/env python3
# -*- coding: utf-8 -*-"

import argparse
import json
import os
import sys
import tempfile
import time
from typing import Optional

import requests
import serial
from intelhex import IntelHex
from platformdirs import user_cache_dir
from pyfu_usb import _get_dfu_devices as dfu_devices
from pyfu_usb import download
from serial.tools.list_ports import comports

from msp import MspCtr, bit_check
from msp_codes import MspCodes
from msp_data import ConfigurationStates, ResetTypes, TargetCapabilitiesFlags


APP_NAME = 'bf_flash'
API_URL = 'https://build.betaflight.com/api'
BAUDRATE = 115200
CUSTOM_DEFAULTS_POINTER_ADDRESS = 0x08002800

_port = None

def detect_port() -> str:
    global _port
    if _port:
        return _port

    while True:
        ports = comports()
        for item in enumerate(ports):
            print(f'{item[0] + 1} - {item[1].name}')
        try:
            rchr = input('Select port or (R) for refresh: ')
            if rchr.lower() == 'r':
                continue

            selected = int(rchr) - 1
            _port = ports[selected].device
            break
        except:
            return None

    if not _port:
        print('ERROR: COM port is not specified', file=sys.stderr)
        sys.exit(-1)

    return _port

def to_dfu_mode(port: Optional[str]):
    if dfu_devices():
        return

    port = port or detect_port()
    com = serial.Serial(port, BAUDRATE)
    com.write(b'#\n')
    time.sleep(0.4)
    com.write(b'bl\n')
    com.close()

def flash(hex_file: str, build_info: dict):
    devices = []
    for _ in range(10):
        devices = dfu_devices()
        if devices:
            break
        print('Wait DFU device…')
        time.sleep(1)

    if not devices:
        print(f'ERROR not found DFU device: {hex_file}', file=sys.stderr)
        sys.exit(-1)

    print(f'Flash: {devices}')

    intel_hex = IntelHex(hex_file)
    config = build_info.get('configuration')

    if build_info and config:
        firmware = intel_hex.todict()
        start = 0
        size = 0
        prk = intel_hex.minaddr()
        for k in sorted(filter(lambda k : isinstance(k, int), firmware)):
            if prk >= CUSTOM_DEFAULTS_POINTER_ADDRESS and k - prk > 1:
                start = prk + 1
                size = k - start
            prk = k

        config = '\n'.join(config)
        config = f'# Betaflight\n${config}\0'
        if start and size and len(config) <= size:
            for b in config:
                firmware[start] = ord(b)
                start += 1
            intel_hex = IntelHex(firmware)

    try:
        bin_tmp = os.path.join(tempfile.gettempdir(), 'betaflight.bin')
        intel_hex.tofile(bin_tmp, 'bin')
        download(bin_tmp, address=intel_hex.minaddr())
    except Exception as e:
        print(f'ERROR Exception: {e}', file=sys.stderr)
    finally:
        os.remove(bin_tmp)

    print('Flash done!')

def apply_custom_defaults(port: Optional[str]):
    port = port or detect_port()
    is_found = False
    for _ in range(10):
        ports = tuple(map(lambda p: p.device, comports()))
        if port in ports:
            is_found = True
            break
        print('Wait COM port…')
        time.sleep(1)

    if not is_found:
        print(f'ERROR not found COM port: {port}', file=sys.stderr)
        sys.exit(-1)

    msp = MspCtr(serial.Serial(port, baudrate=BAUDRATE))
    msp.send(MspCodes.MSP_API_VERSION)
    msp.decode(msp.read_rec())
    msp.send(MspCodes.MSP_FC_VARIANT)
    msp.decode(msp.read_rec())
    msp.send(MspCodes.MSP_FC_VERSION)
    msp.decode(msp.read_rec())
    msp.send(MspCodes.MSP_BUILD_INFO)
    msp.decode(msp.read_rec())
    msp.send(MspCodes.MSP_BOARD_INFO)
    msp.decode(msp.read_rec())

    print(f'{msp.data.target_name} / {msp.data.board_name} / {msp.data.flight_controller_version} / {msp.data.build_info}')

    if bit_check(msp.data.target_capabilities, TargetCapabilitiesFlags.SUPPORTS_CUSTOM_DEFAULTS) \
            and bit_check(msp.data.target_capabilities, TargetCapabilitiesFlags.HAS_CUSTOM_DEFAULTS) \
            and msp.data.configuration_state == ConfigurationStates.DEFAULTS_BARE:
        msp.send(MspCodes.MSP_RESET_CONF, ResetTypes.CUSTOM_DEFAULTS)
        try:
            rec = msp.read_rec()
            print(f'Set defaults done! [{rec}]')
        except:
            print('Set defaults done!')
    else:
        print('SUPPORTS_CUSTOM_DEFAULTS not supported!')

def detect_target(port: Optional[str]) -> str:
    port = port or detect_port()
    msp = MspCtr(serial.Serial(port, baudrate=BAUDRATE))
    msp.send(MspCodes.MSP_BOARD_INFO)
    rec = msp.read_rec()
    msp.decode(rec)
    return msp.data.board_name

def get_release(target: str) -> str:
    response = requests.get(f'{API_URL}/targets/{target}', timeout=10)
    releases = response.json().get('releases')
    if not releases:
        print(f'ERROR: Load releases for target: {target}', file=sys.stderr)
        sys.exit(-1)

    releases = tuple(filter(lambda x: x.get('type') == 'Stable', releases))
    for item in enumerate(releases):
        release = item[1].get('release')
        print(f'{item[0] + 1} - {release}')
    try:
        selected = int(input('Select release: ')) - 1
        return releases[selected].get('release')
    except:
        return None

def get_build_info(target: str, release: str) -> dict:
    release_clean = release.replace('.', '_')
    cache_file = f'cfg_{target}_{release_clean}.json'
    cache_path = user_cache_dir(APP_NAME)

    if not os.path.isdir(cache_path):
        os.mkdir(cache_path)

    cache = os.path.join(user_cache_dir(APP_NAME), cache_file.lower())
    if os.path.isfile(cache) and (time.time() - os.path.getmtime(cache)) < 86400: # One day
        with open(cache, encoding="utf-8") as f:
            print(f'Build info from cache file: {cache}')
            return json.load(f)

    response = requests.get(f'{API_URL}/builds/{release}/{target}', timeout=10)
    obj = response.json()
    with open(cache, 'w', encoding="utf-8") as f:
        json.dump(obj, f)
    return obj

def restore_backup(port: Optional[str], config_file: str):
    port = port or detect_port()
    is_found = False
    for _ in range(10):
        ports = tuple(map(lambda p: p.device, comports()))
        if port in ports:
            is_found = True
            break
        print('Wait COM port…')
        time.sleep(1)

    if not is_found:
        print(f'ERROR not found COM port: {port}', file=sys.stderr)
        sys.exit(-1)

    with open(config_file, encoding='ascii') as f:
        com = serial.Serial(port, 115200)
        com.write(b'#\n')
        time.sleep(0.4)

        for line in f:
            if not line or line == '\n' or line[0] == '#':
                continue
            com.write(line.encode('ascii'))
            time.sleep(0.01)
            rs = com.read_all().decode('ascii')
            if rs and rs != '\n':
                print(rs)

        time.sleep(1)
        com.write(b'save\n')
        time.sleep(0.5)
        rs = com.read_all().decode('ascii')
        if rs and rs != '\n':
            print(rs)
        if 'ERROR' in rs:
            time.sleep(1)
            com.write(b'save\n')
            time.sleep(0.5)
        com.close()
        print('--------------------')
        print('Restore backup done!')

def main() -> None:
    parser = argparse.ArgumentParser(description='Command line Betaflight flasher')
    parser.add_argument('-f', dest='hex', help='Intel HEX firmware file')
    parser.add_argument('-c', dest='cfg', required=False, help='Betaflight config txt file path')
    parser.add_argument('-p', dest='port', required=False, help='COM Port')
    parser.add_argument('-t', dest='target', required=False, help='Betaflight target')
    parser.add_argument('-r', dest='release', required=False, help='Target release version')
    args = parser.parse_args()

    port = args.port

    if args.hex:
        if not os.path.isfile(args.hex):
            print(f'File not fount: {args.hex}', file=sys.stderr)
            sys.exit(-1)
        hex_items = os.path.basename(args.hex).split('_')
        target = hex_items[3] if len(hex_items) > 3 else args.target or detect_target(port)
        if not target:
            print('ERROR: Target is not specified', file=sys.stderr)
            sys.exit(-1)
        release = hex_items[1] if len(hex_items) > 1 else args.release or get_release(target)
        if not release:
            print(f'ERROR: Release for target {args.target} is not selected', file=sys.stderr)
            sys.exit(-1)
        build_info = get_build_info(target, release)
        if not build_info:
            print(f'ERROR: Impossible to get information about target: {target} {release}', file=sys.stderr)
            sys.exit(-1)
        to_dfu_mode(port)
        flash(args.hex, build_info)
        apply_custom_defaults(port)

    if args.cfg:
        if not os.path.isfile(args.cfg):
            print(f'File not fount: {args.hex}', file=sys.stderr)
            sys.exit(-1)
        restore_backup(port, args.cfg)

if __name__ == "__main__":
    main()
