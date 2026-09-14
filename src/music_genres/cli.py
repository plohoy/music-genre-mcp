from __future__ import annotations

import argparse
import json

from .repository import build_style_prompt, ensure_database, resolve, search


def main() -> None:
    parser = argparse.ArgumentParser(prog="music-genres", description="Query the local music genre knowledge base")
    sub = parser.add_subparsers(dest="command", required=True)
    get = sub.add_parser("get")
    get.add_argument("genre")
    find = sub.add_parser("search")
    find.add_argument("query")
    find.add_argument("--limit", type=int, default=10)
    prompt = sub.add_parser("prompt")
    prompt.add_argument("genres", nargs="+")
    prompt.add_argument("--extras", default="")
    args = parser.parse_args()
    ensure_database()
    if args.command == "get":
        result = resolve(args.genre)
    elif args.command == "search":
        result = search(args.query, args.limit)
    else:
        result = build_style_prompt(args.genres, extras=args.extras)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
