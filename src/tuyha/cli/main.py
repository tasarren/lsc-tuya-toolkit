import sys

from tuyha.materializer.workflow import materialize_artifacts
from tuyha.contracts.inputs import InputError

from .args import parse_args
from .create import build_request
from .inspect import dump_db, enckey_path, verify_db


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        match args.command:
            case "create":
                artifacts = materialize_artifacts(build_request(args))
                print(f"Created artifact set: {artifacts.manifest}")
            case "dump":
                dump_db(args.file, enckey_path(args.file, args.enckey), args.output)
                print(f"Wrote private, unredacted JSON: {args.output}")
            case "verify":
                findings = verify_db(args.file, enckey_path(args.file, args.enckey), scratch=args.scratch)
                if findings:
                    for finding in findings:
                        print(f"FAIL {finding}")
                    return 1
                print("PASS DB structure and known record checks" + (" including scratch checks" if args.scratch else ""))
                print("Offline checks do not prove camera boot, TLS connection or RTSP.")
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileExistsError:
        print("error: output exists; choose a new output location", file=sys.stderr)
        return 2
    except OSError:
        print("error: cannot read inputs or write output; check paths and permissions", file=sys.stderr)
        return 2
    except (ValueError, TypeError, OverflowError, KeyError, RecursionError):
        # Third-party and JSON exceptions can contain passwords or decoded bytes.
        print("error: invalid input; check DB/enckey pairing, JSON format and command options", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
