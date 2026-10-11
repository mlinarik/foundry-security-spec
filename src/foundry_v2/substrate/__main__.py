"""Substrate process boundary; network service is gated by foundation readiness."""
import argparse


def main():
    parser = argparse.ArgumentParser(prog="foundry-v2-substrate")
    parser.parse_args()
    parser.error("Authenticated substrate service is not implemented yet; see foundation tasks")


if __name__ == "__main__":
    main()
