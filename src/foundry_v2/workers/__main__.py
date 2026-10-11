"""Workers may only be started by the completed lifecycle controller."""
import argparse


def main():
    parser = argparse.ArgumentParser(prog="foundry-v2-worker")
    parser.parse_args()
    parser.error("Worker role runtime is not implemented yet; see foundation tasks")


if __name__ == "__main__":
    main()
