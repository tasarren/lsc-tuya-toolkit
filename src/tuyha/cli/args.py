import argparse
from pathlib import Path


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # Argument values can contain credentials, including on rejection paths.
        super().error("invalid command arguments; see --help")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = _Parser(prog="tuyha", description="Create, dump and verify Anyka camera databases.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create from scratch or a TuyHA JSON dump")
    create.add_argument("--from", dest="from_json", type=Path)
    create.add_argument("--output-dir", default=Path("sd_card/custom/state"), type=Path,
                        help="state directory (default: sd_card/custom/state); replaces generated files only")
    for option in ("wifi-ssid", "wifi-password", "region", "broker-host",
                   "tls-common-name", "rcs-host", "uuid", "auth-key", "device-id",
                   "psk-key", "product-key", "schema-id", "lan-key", "lan-local-key", "tuya-seed-b64", "enckey-hex"):
        create.add_argument(f"--{option}")
    create.add_argument("--broker-port", type=int)
    create.add_argument("--tls-dns-name", action="append", default=[])
    create.add_argument("--tls-ip-address", action="append", default=["127.0.0.1"])
    create.add_argument("--tls-validity-days", default=365, type=int)
    create.add_argument("--no-rcs-cert-b64", action="store_true")
    create.add_argument("--no-gw-ai-ca-arr", action="store_true")
    for name in ("dump", "verify"):
        command = commands.add_parser(name, help=f"{name} an existing DB with its matching enckey")
        command.add_argument("--file", required=True, type=Path)
        command.add_argument("--enckey", type=Path, help="defaults to matching tuya_enckey sibling")
        if name == "dump":
            command.add_argument("--output", required=True, type=Path, help="new private unredacted JSON file")
        else:
            command.add_argument("--scratch", action="store_true", help="also check TuyHA scratch requirements")
    return parser.parse_args(argv)
