"""Helper: turn a short-lived user token into a long-lived PAGE token + Page ID.

You only need to do the click-step once in Meta's Graph API Explorer:
  https://developers.facebook.com/tools/explorer/
  1. Pick your app (top right).
  2. "User or Page" -> User Token.
  3. Add permissions:  pages_show_list, pages_manage_posts, pages_read_engagement
  4. Click "Generate Access Token", approve, and copy the token.

Then run:
  python get_token.py --app-id APPID --app-secret APPSECRET --user-token TOKEN
  # optional: --page thestatepostnews   (filters to one page by name/slug)

It prints the FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN lines ready for your .env.
Page tokens minted from a long-lived user token are effectively non-expiring.
"""
from __future__ import annotations

import argparse
import sys

import requests

GRAPH = "https://graph.facebook.com/v21.0"


def _get(path: str, **params) -> dict:
    r = requests.get(f"{GRAPH}/{path}", params=params, timeout=30)
    data = r.json()
    if "error" in data:
        sys.exit(f"Graph API error: {data['error']}")
    return data


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--app-id", required=True)
    p.add_argument("--app-secret", required=True)
    p.add_argument("--user-token", required=True, help="short-lived user token from Graph Explorer")
    p.add_argument("--page", help="optional page name/slug to filter to one page")
    args = p.parse_args()

    # 1. short-lived user token -> long-lived user token
    longlived = _get(
        "oauth/access_token",
        grant_type="fb_exchange_token",
        client_id=args.app_id,
        client_secret=args.app_secret,
        fb_exchange_token=args.user_token,
    )["access_token"]
    print("✓ Got long-lived user token", file=sys.stderr)

    # 2. list pages this user manages -> each comes with its own page token
    pages = _get("me/accounts", access_token=longlived, fields="id,name,access_token").get("data", [])
    if not pages:
        sys.exit("No Pages found for this user. Make sure you granted pages_show_list and admin the Page.")

    if args.page:
        q = args.page.lower()
        pages = [pg for pg in pages if q in pg["name"].lower()] or pages

    print("\nPages found:", file=sys.stderr)
    for pg in pages:
        print(f"  - {pg['name']}  (id={pg['id']})", file=sys.stderr)

    target = pages[0]
    print(f"\n# --- paste into .env  (page: {target['name']}) ---")
    print(f"FB_PAGE_ID={target['id']}")
    print(f"FB_PAGE_ACCESS_TOKEN={target['access_token']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
