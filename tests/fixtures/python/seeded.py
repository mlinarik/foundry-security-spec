"""Intentionally unsafe fixture. Never import or execute this target."""
import subprocess


def run_command(untrusted):
    return subprocess.run(untrusted, shell=True)
