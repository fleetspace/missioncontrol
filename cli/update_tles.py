#!/usr/bin/env python

import json
import re
from datetime import datetime, timedelta
import logging

import requests

from mcapi import MCAPI, get_parser, handle_default_args


def get_active():
    """
    Get current list of satellites from celestrak
    Cache it to disk so we're quicker and don't hit it too often (just in case)
    """
    now = datetime.now()
    filename = '/tmp/celestrack-active.txt'
    date_format = '%d %b %Y %H:%M:%S.%f'
    hours_to_cache = 1
    try:
        with open(filename) as obj:
            data = json.load(obj)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {
            'date':
            (now - timedelta(hours=hours_to_cache + 1)).strftime(date_format)
        }

    date = datetime.strptime(data.get('date'), date_format)
    if (now - date).total_seconds() > hours_to_cache * 60 * 60:
        active = requests.get(
            'https://celestrak.com/NORAD/elements/active.txt').text
        with open(filename, 'w') as obj:
            json.dump({
                'date': now.strftime(date_format),
                'active': active,
            }, obj)
            return active
    else:
        return data.get('active')


def update_tles(args):
    active = get_active()

    for satellite in args.mc_api.get_satellites():
        catid = satellite['catid']
        ret = re.findall(f'\r\n(.*)\r\n(2 {catid}.*)\r\n', active)
        if len(ret) != 1:
            logging.warn(f"Unknown catalougue ID: {catid}")
            continue
        line1 = ret[0][0]
        line2 = ret[0][1]

        args.mc_api.patch_satellite(hwid=satellite['hwid'], tle=[line1, line2])



def main():
    parser = get_parser()
    parser.set_defaults(func=update_tles)

    # Parse the args and call the function
    args = parser.parse_args()
    if not args.func:
        parser.print_help()
        exit(1)

    handle_default_args(args)

    try:
        args.func(args)
    except requests.HTTPError as e:
        print(json.dumps(e.response.json(), indent=4))
        raise


if __name__ == '__main__':
    main()
