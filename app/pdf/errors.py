class PdfError(Exception):
    """A recoverable PDF error that can be shown to the user."""

    status_code = 503


class PdfInputError(PdfError):
    status_code = 422
