"""Local package information; operational commands arrive with their stories."""
import argparse
from foundry_v2 import __version__
from foundry_v2.roles.registry import Role


def main():
    parser = argparse.ArgumentParser(prog="foundry-v2")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("roles", help="List the eight core role identities")
    args = parser.parse_args()
    if args.command == "roles":
        print("\n".join(Role))


if __name__ == "__main__":
    main()
