#!/usr/bin/env python

import argparse
import os
import sys
import json
import uuid

from mcapi import MCAPI, get_parser, handle_default_args
from requests import HTTPError
from tabulate import tabulate


def _make_rows(data, headers, defaults={}):
    """ extract the values from the data based on the headers
        data is a list of dicts
        headers is a list of keys
        defaults is a dict, where the keys are from the headers list

        returns the data in a list or rows (tabulate data format)
    """
    table_data = []
    for o in data:
        table_data.append(
            [o.get(k, defaults.get(k)) for k in headers]
        )
    return table_data


def list_all(args):
    query = {}
    if args.satellites:
        query["satellites"] = args.satellites
    if args.groundstations:
        query["groundstations"] = args.groundstations

    accesses = args.mc_api.get_accesses(**query)

    if args.all:
        query["show_stale"] = True

    passes = args.mc_api.get_passes(**query)

    headers = ["t", "satellite", "groundstation",
               "start_time", "end_time", "max_alt"]
    table_data = []
    table_data += _make_rows(accesses, headers + ["id"], {"t": "a"})
    table_data += _make_rows(passes, headers + ["uuid"], {"t": "p"})
    if table_data:
        table_data = sorted(
            table_data,
            key=lambda w: w[headers.index("start_time")]
        )
    print(tabulate(table_data, headers=headers + ["id"]))


def list_passes(args):
    query = {}
    if args.satellites:
        query["satellites"] = args.satellites
    if args.groundstations:
        query["groundstations"] = args.groundstations
    if args.all:
        query["show_stale"] = True
    passes = args.mc_api.get_passes(**query)
    for _pass in passes:
        _pass["t"] = "p" if _pass["is_desired"] else "-"
    table_headers = ["t", "satellite", "groundstation",
                     "start_time", "end_time", "max_alt", "uuid"]
    table_data = _make_rows(passes, table_headers)
    print(tabulate(table_data, headers=table_headers))


def list_accesses(args):
    query = {}
    if args.satellites:
        query["satellites"] = args.satellites
    if args.groundstations:
        query["groundstations"] = args.groundstations
    if args.range_start:
        query["range_start"] = args.range_start
    if args.range_end:
        query["range_end"] = args.range_end
    accesses = args.mc_api.get_accesses(**query)
    table_headers = ["t", "satellite", "groundstation",
                     "start_time", "end_time", "max_alt", "id"]
    table_data = _make_rows(accesses, table_headers, {"t": "a"})
    print(tabulate(table_data, headers=table_headers))


def create_pass_from_access(args):
    new_pass = args.mc_api.put_pass(
        args.pass_id,
        access_id=args.access_id
    )
    print(json.dumps(new_pass, indent=4))


def create_pass_from_times(args):
    new_pass = args.mc_api.put_pass(
        args.pass_id,
        satellite=args.satellite,
        groundstation=args.groundstation,
        start_time=args.start_time,
        end_time=args.end_time
    )
    print(json.dumps(new_pass, indent=4))


def set_pass_field(args):
    kwargs = {args.key: args.val}
    _pass = args.mc_api.patch_pass(args.pass_id, **kwargs)
    print(json.dumps(_pass, indent=4))


def cancel_pass(args):
    _pass = args.mc_api.patch_pass(
        args.pass_id,
        is_desired=False
    )
    print(json.dumps(_pass, indent=4))


def uncancel_pass(args):
    _pass = args.mc_api.patch_pass(
        args.pass_id,
        is_desired=True
    )
    print(json.dumps(_pass, indent=4))


def delete_pass(args):
    args.mc_api.delete_pass(args.pass_id)


def main():
    parser = get_parser()

    parser.set_defaults(func=False)

    subparsers = parser.add_subparsers(
        title='subcommands',
        description='valid subcommands',
        help='additional help')

    # Define the 'list' commands
    list_parser = subparsers.add_parser('list')
    list_parser.set_defaults(func=list_all)
    list_parser.add_argument("--satellites",
                             help="csv satellite hwids")
    list_parser.add_argument("--groundstations",
                             help="csv groundstation hwids")
    list_parser.add_argument("--all",
                             action="store_true",
                             help="also shows stale passes")

    list_passes_parser = subparsers.add_parser('list_passes')
    list_passes_parser.set_defaults(func=list_passes)
    list_passes_parser.add_argument("--satellites",
                                    help="csv satellite hwids")
    list_passes_parser.add_argument("--groundstations",
                                    help="csv groundstation hwids")
    list_passes_parser.add_argument("--all",
                                    action="store_true",
                                    help="also shows stale passes")

    list_accesses_parser = subparsers.add_parser('list_accesses')
    list_accesses_parser.set_defaults(func=list_accesses)
    list_accesses_parser.add_argument("--satellites",
                                      help="csv satellite hwids")
    list_accesses_parser.add_argument("--groundstations",
                                      help="csv groundstation hwids")
    list_accesses_parser.add_argument(
        "--range_start",
        help="ISO8601 date format, find accesses after this datetime. "
        "Defaults to now."
    )
    list_accesses_parser.add_argument(
        "--range_end",
        help="ISO8601 date format, find accesses up until this datetime. "
        "Defaults to now + 2 days"
    )

    # Define the 'create' command
    create_parser = subparsers.add_parser('create')
    create_parser.set_defaults(func=create_pass_from_access)
    create_parser.add_argument(
           "--pass-id",
           default=uuid.uuid4(),
           type=uuid.UUID)
    create_parser.add_argument('access_id', metavar='access-id')

    tcreate_parser = subparsers.add_parser('create_from_times')
    tcreate_parser.set_defaults(func=create_pass_from_times)
    tcreate_parser.add_argument("satellite", help="the satellite hwid")
    tcreate_parser.add_argument("groundstation", help="the groundstation hwid")
    tcreate_parser.add_argument(
        "start_time", metavar="start-time", help="ISO8601 timestamp")
    tcreate_parser.add_argument(
        "end_time", metavar="end-time", help="ISO8601 timestamp")
    tcreate_parser.add_argument(
        "--pass-id", default=uuid.uuid4(), type=uuid.UUID)

    # Define the 'cancel' command
    cancel_parser = subparsers.add_parser('cancel')
    cancel_parser.add_argument("pass_id", metavar="pass-id", type=uuid.UUID)
    cancel_parser.set_defaults(func=cancel_pass)

    # Define the 'uncancel' command
    uncancel_parser = subparsers.add_parser('uncancel')
    uncancel_parser.add_argument("pass_id", metavar="pass-id", type=uuid.UUID)
    uncancel_parser.set_defaults(func=uncancel_pass)

    # Define the 'delete' command
    delete_parser = subparsers.add_parser('delete')
    delete_parser.add_argument("pass_id", metavar="pass-id", type=uuid.UUID)
    delete_parser.set_defaults(func=delete_pass)

    # Define the 'set-flag' command
    set_parser = subparsers.add_parser('set-flag')
    set_parser.add_argument("pass_id", metavar="pass-id", type=uuid.UUID)
    set_parser.add_argument(
        "key",
        help="marks boolean fields as True, prepend with 'un' to mark as False"
             ", for example 'mark undesired'")
    set_parser.add_argument(
        "val",
        type=bool,
    )
    set_parser.set_defaults(func=set_pass_field)

    # Parse the args and call the function
    args = parser.parse_args()
    if not args.func:
        parser.print_help()
        exit(1)

    handle_default_args(args)

    try:
        args.func(args)
    except HTTPError as e:
        print(json.dumps(e.response.json(), indent=4))
        exit(e.response.status_code)


if __name__ == '__main__':
    main()
