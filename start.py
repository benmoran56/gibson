import argparse

import gibson

parser = argparse.ArgumentParser(description="Start the Server")
parser.add_argument('--addr', default='0.0.0.0', help="listen address (defaults to 0.0.0.0)")
parser.add_argument('--port', type=int, default=6400, help="listen port (defaults to 6400)")
parser.add_argument('--bitrate', type=int, default=9600, help="set the bitrate (defaults to 9600)")
args = parser.parse_args()


if __name__ == "__main__":
    server = gibson.Server(args.addr, args.port, args.bitrate)
    server.run()
