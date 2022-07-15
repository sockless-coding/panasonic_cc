import argparse
import json
import pcomfortcloud

from enum import Enum

def print_result(obj, indent = 0):
    for key in obj:
        value = obj[key]

        if isinstance(value, dict):
            print(" "*indent + key)
            print_result(value, indent + 4)
        elif isinstance(value, Enum):
            print(" "*indent + "{0: <{width}}: {1}".format(key, value.name, width=25-indent))
        elif isinstance(value, list):
            print(" "*indent + "{0: <{width}}:".format(key, width=25-indent))
            for elt in value:
                print_result(elt, indent + 4)
                print("")
        else:
            print(" "*indent + "{0: <{width}}: {1}".format(key, value, width=25-indent))

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def main():
    """ Start pcomfortcloud Comfort Cloud command line """

    parser = argparse.ArgumentParser(
        description='Read or change status of pcomfortcloud Climate devices')

    parser.add_argument(
        'username',
        help='Username for pcomfortcloud Comfort Cloud')

    parser.add_argument(
        'password',
        help='Password for pcomfortcloud Comfort Cloud')

    parser.add_argument(
        '-t', '--token',
        help='File to store token in',
        default='~/.pcomfortcloud-token')

    parser.add_argument(
        '-s', '--skipVerify',
        help='Skip Ssl verification if set as True',
        type=str2bool, nargs='?', const=True,
        default=False)

    parser.add_argument(
        '-r', '--raw',
        help='Raw dump of response',
        type=str2bool, nargs='?', const=True,
        default=False)

    commandparser = parser.add_subparsers(
        help='commands',
        dest='command')

    commandparser.add_parser(
        'list',
        help="Get a list of all devices")

    get_parser = commandparser.add_parser(
        'get',
        help="Get status of a device")

    get_parser.add_argument(
        dest='device',
        type=int,
        help='Device number #')

    set_parser = commandparser.add_parser(
        'set',
        help="Set status of a device")

    set_parser.add_argument(
        dest='device',
        type=int,
        help='Device number #'
    )

    set_parser.add_argument(
        '-p', '--power',
        choices=[
            pcomfortcloud.constants.Power.On.name,
            pcomfortcloud.constants.Power.Off.name],
        help='Power mode')

    set_parser.add_argument(
        '-t', '--temperature',
        type=float,
        help="Temperature")

    set_parser.add_argument(
        '-f', '--fanSpeed',
        choices=[
            pcomfortcloud.constants.FanSpeed.Auto.name,
            pcomfortcloud.constants.FanSpeed.Low.name,
            pcomfortcloud.constants.FanSpeed.LowMid.name,
            pcomfortcloud.constants.FanSpeed.Mid.name,
            pcomfortcloud.constants.FanSpeed.HighMid.name,
            pcomfortcloud.constants.FanSpeed.High.name],
        help='Fan speed')

    set_parser.add_argument(
        '-m', '--mode',
        choices=[
            pcomfortcloud.constants.OperationMode.Auto.name,
            pcomfortcloud.constants.OperationMode.Cool.name,
            pcomfortcloud.constants.OperationMode.Dry.name,
            pcomfortcloud.constants.OperationMode.Heat.name,
            pcomfortcloud.constants.OperationMode.Fan.name],
        help='Operation mode')

    set_parser.add_argument(
        '-e', '--eco',
        choices=[
            pcomfortcloud.constants.EcoMode.Auto.name,
            pcomfortcloud.constants.EcoMode.Quiet.name,
            pcomfortcloud.constants.EcoMode.Powerful.name],
        help='Eco mode')

    set_parser.add_argument(
        '-n', '--nanoe',
        choices=[
            pcomfortcloud.constants.NanoeMode.On.name,
            pcomfortcloud.constants.NanoeMode.Off.name,
            pcomfortcloud.constants.NanoeMode.ModeG.name,
            pcomfortcloud.constants.NanoeMode.All.name],
        help='Nanoe mode')

    # set_parser.add_argument(
    #     '--airswingauto',
    #     choices=[
    #         pcomfortcloud.constants.AirSwingAutoMode.Disabled.name,
    #         pcomfortcloud.constants.AirSwingAutoMode.AirSwingLR.name,
    #         pcomfortcloud.constants.AirSwingAutoMode.AirSwingUD.name,
    #         pcomfortcloud.constants.AirSwingAutoMode.Both.name],
    #     help='Automation of air swing')

    set_parser.add_argument(
        '-y', '--airSwingVertical',
        choices=[
            pcomfortcloud.constants.AirSwingUD.Auto.name,
            pcomfortcloud.constants.AirSwingUD.Down.name,
            pcomfortcloud.constants.AirSwingUD.DownMid.name,
            pcomfortcloud.constants.AirSwingUD.Mid.name,
            pcomfortcloud.constants.AirSwingUD.UpMid.name,
            pcomfortcloud.constants.AirSwingUD.Up.name],
        help='Vertical position of the air swing')

    set_parser.add_argument(
        '-x', '--airSwingHorizontal',
        choices=[
            pcomfortcloud.constants.AirSwingLR.Auto.name,
            pcomfortcloud.constants.AirSwingLR.Left.name,
            pcomfortcloud.constants.AirSwingLR.LeftMid.name,
            pcomfortcloud.constants.AirSwingLR.Mid.name,
            pcomfortcloud.constants.AirSwingLR.RightMid.name,
            pcomfortcloud.constants.AirSwingLR.Right.name],
        help='Horizontal position of the air swing')

    dump_parser = commandparser.add_parser(
        'dump',
        help="Dump data of a device")

    dump_parser.add_argument(
        dest='device',
        type=int,
        help='Device number 1-x')

    history_parser = commandparser.add_parser(
        'history',
        help="Dump history of a device")

    history_parser.add_argument(
        dest='device',
        type=int,
        help='Device number 1-x')

    history_parser.add_argument(
        dest='mode',
        type=str,
        help='mode (Day, Week, Month, Year)')

    history_parser.add_argument(
        dest='date',
        type=str,
        help='date of day like 20190807')

    args = parser.parse_args()

    session = pcomfortcloud.Session(args.username, args.password, args.token, args.raw, args.skipVerify == False)
    session.login()
    try:
        if args.command == 'list':
            print("list of devices and its device id (1-x)")
            for idx, device in enumerate(session.get_devices()):
                if(idx > 0):
                    print('')

                print("device #{}".format(idx + 1))
                print_result(device, 4)

        if args.command == 'get':
            if int(args.device) <= 0 or int(args.device) > len(session.get_devices()):
                raise Exception("device not found, acceptable device id is from {} to {}".format(1, len(session.get_devices())))

            device = session.get_devices()[int(args.device) - 1]
            print("reading from device '{}' ({})".format(device['name'], device['id']))

            print_result( session.get_device(device['id']) )

        if args.command == 'set':
            if int(args.device) <= 0 or int(args.device) > len(session.get_devices()):
                raise Exception("device not found, acceptable device id is from {} to {}".format(1, len(session.get_devices())))

            device = session.get_devices()[int(args.device) - 1]
            print("writing to device '{}' ({})".format(device['name'], device['id']))

            kwargs = {}

            if args.power is not None:
                kwargs['power'] = pcomfortcloud.constants.Power[args.power]

            if args.temperature is not None:
                kwargs['temperature'] = args.temperature

            if args.fanSpeed is not None:
                kwargs['fanSpeed'] = pcomfortcloud.constants.FanSpeed[args.fanSpeed]

            if args.mode is not None:
                kwargs['mode'] = pcomfortcloud.constants.OperationMode[args.mode]

            if args.eco is not None:
                kwargs['eco'] = pcomfortcloud.constants.EcoMode[args.eco]

            if args.nanoe is not None:
                kwargs['nanoe'] = pcomfortcloud.constants.NanoeMode[args.nanoe]

            if args.airSwingHorizontal is not None:
                kwargs['airSwingHorizontal'] = pcomfortcloud.constants.AirSwingLR[args.airSwingHorizontal]

            if args.airSwingVertical is not None:
                kwargs['airSwingVertical'] = pcomfortcloud.constants.AirSwingUD[args.airSwingVertical]

            session.set_device(device['id'], **kwargs)

        if args.command == 'dump':
            if int(args.device) <= 0 or int(args.device) > len(session.get_devices()):
                raise Exception("device not found, acceptable device id is from {} to {}".format(1, len(session.get_devices())))

            device = session.get_devices()[int(args.device) - 1]

            print_result(session.dump(device['id']))

        if args.command == 'history':
            if int(args.device) <= 0 or int(args.device) > len(session.get_devices()):
                raise Exception("device not found, acceptable device id is from {} to {}".format(1, len(session.get_devices())))

            device = session.get_devices()[int(args.device) - 1]

            print_result(session.history(device['id'], args.mode, args.date))

    except pcomfortcloud.ResponseError as ex:
        print(ex.text)


# pylint: disable=C0103
if __name__ == "__main__":
    main()
