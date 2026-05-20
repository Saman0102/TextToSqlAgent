#!/usr/bin/env python3
"""Application entrypoint for the Text-to-SQL app."""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
	sys.path.insert(0, str(APP_DIR))


def _ensure_streamlit_starlette_compat() -> None:
	try:
		import starlette.middleware.gzip as _gzip
		if not hasattr(_gzip, 'DEFAULT_EXCLUDED_CONTENT_TYPES'):
			_gzip.DEFAULT_EXCLUDED_CONTENT_TYPES = ('text/event-stream',)
		if not hasattr(_gzip, 'IdentityResponder'):
			class IdentityResponder:
				def __init__(self, app, minimum_size=0, compresslevel=9):
					self.app = app

				async def __call__(self, scope, receive, send):
					await self.app(scope, receive, send)

			_gzip.IdentityResponder = IdentityResponder
	except Exception:
		pass


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description='Text-to-SQL app runner')
	subparsers = parser.add_subparsers(dest='command')

	serve_parser = subparsers.add_parser('serve', help='Launch the Streamlit UI')
	serve_parser.add_argument('--host', default='0.0.0.0', help='Host interface to bind')
	serve_parser.add_argument('--port', type=int, default=8501, help='Port to bind')

	return parser


def _run_streamlit(host: str, port: int) -> int:
	venv_python = APP_DIR.parents[2] / '.venv' / 'bin' / 'python'
	if not venv_python.exists():
		venv_python = APP_DIR.parents[1] / '.venv' / 'bin' / 'python'
	_ensure_streamlit_starlette_compat()
	try:
		import streamlit.web.cli as stcli
	except ModuleNotFoundError:
		if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
			os.execv(str(venv_python), [str(venv_python), str(APP_DIR / 'main.py'), 'serve', '--host', host, '--port', str(port)])
		raise RuntimeError(
			'Streamlit is not installed in the active Python interpreter. '
			'Run the app with the workspace venv at /home/saman/FuseMachine/.venv/bin/python '
			'or install streamlit in the current environment.'
		)
	sys.argv = [
		'streamlit',
		'run',
		str(APP_DIR / 'streamlit_app.py'),
		'--server.address',
		host,
		'--server.port',
		str(port),
	]
	return stcli.main()


def main(argv: Optional[Sequence[str]] = None) -> int:
	parser = _build_parser()
	argv = list(sys.argv[1:] if argv is None else argv)
	if not argv:
		parser.print_help()
		return 2
	if argv[0] != 'serve':
		argv = ['serve', *argv]
	args = parser.parse_args(argv)
	return _run_streamlit(args.host, args.port)


if __name__ == '__main__':
	raise SystemExit(main())