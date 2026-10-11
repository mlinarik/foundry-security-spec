"""Orchestrator process boundary. Do not silently start an incomplete fleet."""
import argparse


def main():
    parser = argparse.ArgumentParser(prog="foundry-v2-orchestrator")
    parser.parse_args()
    parser.error("Orchestrator lifecycle is not implemented yet; see US1 tasks")


if __name__ == "__main__":
    main()
