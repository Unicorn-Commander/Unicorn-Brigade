"""
Request size limit helpers.
"""

from fastapi import Depends, HTTPException, Request, status


def max_body_size(max_bytes: int):
    """
    FastAPI dependency that enforces a max request body size.
    """
    async def _dependency(request: Request) -> None:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Request body too large (max {max_bytes} bytes)",
                    )
            except ValueError:
                pass

        body = await request.body()
        if len(body) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Request body too large (max {max_bytes} bytes)",
            )

    return Depends(_dependency)
