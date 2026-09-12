"""Style stacks and speech rendering; independent of editor text and colours."""

from __future__ import annotations

from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
	from speech.commands import SpeechCommand


from pathlib import Path
from wave import Error as WaveError

from logHandler import log
from speech.commands import WaveFileCommand

from . import _, syntaxMode, getSoundVolume
from .soundVolume import scaledSoundPath

SyntaxKind = Literal["quoted text", "text substitution", "Inform 6 code", "heading", "comment"]
SyntaxStack = tuple[SyntaxKind, ...]
SyntaxEvent = tuple[Literal["begin", "end"], SyntaxKind]


SOUND_DIRECTORY = Path(__file__).resolve().parents[2] / "sounds"
SOUND_NAMES = {
	"quoted text": "quote",
	"text substitution": "substitution",
	"heading": "heading",
	"comment": "comment",
	# No dedicated Inform 6 pair was supplied; reuse the comment boundary cues.
	"Inform 6 code": "comment",
}
_missingSounds: set[str] = set()


def styleStack(style: int) -> SyntaxStack:
	style &= 0x1F
	if style == 1:
		return ("quoted text",)
	if style == 2:
		return ("quoted text", "text substitution")
	if style == 3:
		return ("Inform 6 code",)
	if style == 4:
		return ("heading",)
	if 5 <= style <= 20:
		return ("comment",) * (style - 4)
	return ()


def stackEvents(before: SyntaxStack, after: SyntaxStack) -> list[SyntaxEvent]:
	common = 0
	while common < min(len(before), len(after)) and before[common] == after[common]:
		common += 1
	events: list[SyntaxEvent] = [("end", kind) for kind in reversed(before[common:])]
	events.extend(("begin", kind) for kind in after[common:])
	return events


def renderMarker(event: SyntaxEvent) -> list[str | SpeechCommand]:
	"""Queue the cue at the same boundary as speech, with NVDA cancellation.

	No audio is played during text extraction or ahead of the speech queue.
	In combined mode, the sound starts immediately before the spoken marker.
	"""
	mode = syntaxMode()
	if mode == "none":
		return []
	# Full strings allow translators to choose natural word order for each marker.
	labels = {
		("begin", "quoted text"): _("Begin quoted text"),
		("end", "quoted text"): _("End quoted text"),
		("begin", "text substitution"): _("Begin text substitution"),
		("end", "text substitution"): _("End text substitution"),
		("begin", "Inform 6 code"): _("Begin Inform 6 code"),
		("end", "Inform 6 code"): _("End Inform 6 code"),
		("begin", "heading"): _("Begin heading"),
		("end", "heading"): _("End heading"),
		("begin", "comment"): _("Begin comment"),
		("end", "comment"): _("End comment"),
	}
	sequence: list[str | SpeechCommand] = []
	volume = getSoundVolume()
	if mode in ("speechAndSounds", "sounds") and volume > 0:
		prefix = SOUND_NAMES.get(event[1])
		if prefix:
			suffix = "start" if event[0] == "begin" else "end"
			path = SOUND_DIRECTORY / f"{prefix}_{suffix}.wav"
			if path.is_file():
				try:
					sequence.append(
						WaveFileCommand(
							str(scaledSoundPath(path, volume)),
						),
					)
				except (OSError, ValueError, EOFError, WaveError):
					# Never fall back to full-volume playback after attenuation fails.
					if path.name not in _missingSounds:
						_missingSounds.add(path.name)
						log.warning(
							"Inform 7 Access: unable to prepare syntax sound: %s",
							path.name,
						)
			elif path.name not in _missingSounds:
				_missingSounds.add(path.name)
				log.warning(
					"Inform 7 Access: syntax sound unavailable: %s",
					path.name,
				)
	if mode in ("speech", "speechAndSounds"):
		sequence.append(labels[event])
	return sequence
