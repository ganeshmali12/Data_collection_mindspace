import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


def build_audio_filter_chain(
    lowcut: int = 80,
    highcut: int = 8000,
    enable_denoise: bool = True,
    enable_silence_trim: bool = True,
    silence_threshold_db: int = -35,
) -> str:
    """
    Build an FFmpeg audio filter chain for voice phonation processing:
    1. Highpass filter (cuts low rumble < lowcut Hz)
    2. Lowpass filter (cuts high hiss > highcut Hz)
    3. FFT Spectral Denoising (afftdn) to suppress stationary noise
    4. Silence trimming (removes dead air before and after vocalization)
    5. Normalization (dynaudnorm / loudnorm)
    """
    filters = []

    # 1. Bandpass / Human vocal range filtering
    if lowcut > 0:
        filters.append(f"highpass=f={lowcut}")
    if highcut > 0:
        filters.append(f"lowpass=f={highcut}")

    # 2. Spectral noise reduction (FFmpeg adaptive FFT denoiser)
    if enable_denoise:
        # nr=12 (12dB noise reduction), nf=-30 (noise floor estimate)
        filters.append("afftdn=nr=12:nf=-30:tn=1")

    # 3. Trim leading & trailing silence
    if enable_silence_trim:
        filters.append(
            f"silenceremove=start_periods=1:start_duration=0.08:start_threshold={silence_threshold_db}dB:"
            f"stop_periods=1:stop_duration=0.2:stop_threshold={silence_threshold_db}dB"
        )

    # 4. Normalize level for consistent vocal feature extraction
    filters.append("dynaudnorm=f=150:g=15:m=10.0")

    return ",".join(filters)


def clean_audio_file(
    input_path: str,
    output_path: str = None,
    target_sr: int = 16000,
    lowcut: int = 80,
    highcut: int = 8000,
    enable_denoise: bool = True,
    enable_silence_trim: bool = True,
) -> str:
    """
    Cleans an input audio file (e.g. webm/wav), applies DSP filtering and noise reduction,
    and exports a 16-bit mono PCM WAV file at target_sr.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Audio input file not found: {input_path}")

    if output_path is None:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        output_path = temp_file.name
        temp_file.close()

    filter_chain = build_audio_filter_chain(
        lowcut=lowcut,
        highcut=highcut,
        enable_denoise=enable_denoise,
        enable_silence_trim=enable_silence_trim,
    )

    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-af", filter_chain,
        "-ar", str(target_sr),
        "-ac", "1",
        "-c:a", "pcm_s16le",
        output_path,
    ]

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return output_path
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is required for audio cleaning and filtering.") from exc
    except subprocess.CalledProcessError as exc:
        logger.error("FFmpeg audio cleaning error: %s", exc.stderr)
        # Fallback: if silenceremove stripped all audio or failed, try basic bandpass without silence trim
        try:
            fallback_filters = f"highpass=f={lowcut},lowpass=f={highcut},afftdn=nr=10"
            fallback_cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-af", fallback_filters,
                "-ar", str(target_sr), "-ac", "1", "-c:a", "pcm_s16le",
                output_path
            ]
            subprocess.run(fallback_cmd, check=True, capture_output=True, text=True)
            return output_path
        except Exception:
            raise RuntimeError(f"Could not clean audio file: {exc.stderr}") from exc


def combine_and_clean_captures(captures, target_sr: int = 16000) -> str:
    """
    Takes a list of MediaCapture objects, cleans each phonation sound segment,
    concatenates them into a standardized phonation session WAV, and returns the path.
    """
    if not captures:
        raise ValueError("No audio captures provided to combine.")

    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    temp_cleaned_files = []

    try:
        for index, capture in enumerate(captures):
            if not capture.file or not os.path.exists(capture.file.path):
                continue
            cleaned = clean_audio_file(
                capture.file.path,
                target_sr=target_sr,
                lowcut=80,
                highcut=8000,
                enable_denoise=True,
                enable_silence_trim=True,
            )
            temp_cleaned_files.append(cleaned)

        if not temp_cleaned_files:
            raise RuntimeError("No valid phonation audio files could be processed.")

        # Concatenate all cleaned phonation segments
        command = ["ffmpeg", "-y"]
        for cleaned_path in temp_cleaned_files:
            command.extend(["-i", cleaned_path])

        inputs = "".join(f"[{idx}:a]" for idx in range(len(temp_cleaned_files)))
        command.extend([
            "-filter_complex", f"{inputs}concat=n={len(temp_cleaned_files)}:v=0:a=1[out]",
            "-map", "[out]",
            "-ar", str(target_sr),
            "-ac", "1",
            "-c:a", "pcm_s16le",
            output_path,
        ])

        subprocess.run(command, check=True, capture_output=True, text=True)
        return output_path
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is required to combine phonation audio.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Could not combine cleaned phonation recordings.") from exc
    finally:
        for temp_file in temp_cleaned_files:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
