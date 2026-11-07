"""One wording for download progress, shared by every tab that shows it."""
from ..system import fmt_bytes, fmt_speed, fmt_eta
from .theme import ACCENT, SUCCESS, ERROR, TEXT_DIM


def status_text(item, short_error: bool = True) -> tuple[str, str]:
    """(text, colour) describing where a download is."""
    s = item.status
    pl = f"Song {item.playlist_pos} of {item.playlist_total}  ·  " if item.playlist_total > 1 else ""
    if s == "downloading" and item.cancel_requested:
        return "Cancelling...", TEXT_DIM
    if s == "downloading" and item.stage == "processing":
        return pl + "Finishing up (converting)...", ACCENT
    if s == "downloading":
        parts = [f"{item.progress*100:.1f}%" if item.progress else
                 (fmt_bytes(item.total) if item.total else "Starting...")]
        if item.speed:
            parts.append(fmt_speed(item.speed))
        if item.eta:
            parts.append(f"ETA {fmt_eta(item.eta)}")
        return pl + "  ".join(parts), ACCENT
    if s == "done":
        size = f"  {fmt_bytes(item.total)}" if item.total and not item.playlist_total else ""
        return f"Done{size}", SUCCESS
    if s == "error":
        err = item.error.splitlines()[0][:80] if short_error else item.error
        return f"Error: {err}", ERROR
    if s == "cancelled":
        return "Cancelled", TEXT_DIM
    return f"Queued · {item.added}", TEXT_DIM
