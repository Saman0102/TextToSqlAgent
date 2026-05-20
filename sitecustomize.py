"""Compatibility shim loaded automatically at Python startup.

Streamlit 1.57 expects ``starlette.middleware.gzip.DEFAULT_EXCLUDED_CONTENT_TYPES``
to exist. Some installed Starlette builds do not expose that symbol, which causes
``streamlit run`` to fail during import. This shim restores the attribute early
enough for Streamlit to import cleanly.
"""

from __future__ import annotations

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
	# If Starlette is unavailable or behaves unexpectedly, leave startup alone.
	pass
