"""Genera un sonido de notificación corto (∼0.3s) en formato WAV.

Este script genera un tono senoidal simple de 440Hz (nota La4)
con un fade-in/fade-out suave para que suene agradable como
notificación de nuevos correos.

El archivo se guarda en shared/sounds/notify.wav.

Uso:
    python scripts/generate_notify_sound.py
"""

import wave
import struct
import math
from pathlib import Path


def generate_notify_wav(output_path: str, duration_sec: float = 0.3,
                        frequency: float = 660.0, sample_rate: int = 44100,
                        volume: float = 0.5) -> None:
    """Genera un archivo WAV con un tono senoidal simple.

    Parameters
    ----------
    output_path : str
        Ruta donde guardar el archivo WAV.
    duration_sec : float
        Duración del tono en segundos.
    frequency : float
        Frecuencia del tono en Hz.
    sample_rate : int
        Tasa de muestreo en Hz.
    volume : float
        Volumen (0.0 a 1.0).
    """
    num_samples = int(sample_rate * duration_sec)
    samples = []

    for i in range(num_samples):
        t = i / sample_rate  # tiempo en segundos

        # Envelope: fade-in (10%) y fade-out (20%)
        fade_in_len = int(num_samples * 0.1)
        fade_out_len = int(num_samples * 0.2)
        if i < fade_in_len:
            env = i / fade_in_len
        elif i > num_samples - fade_out_len:
            env = (num_samples - i) / fade_out_len
        else:
            env = 1.0

        # Generar muestra senoidal con armónico (más agradable)
        value = math.sin(2 * math.pi * frequency * t)
        # Agregar un armónico suave (una octava arriba, volumen reducido)
        value += 0.3 * math.sin(2 * math.pi * frequency * 2 * t)

        # Normalizar y aplicar envelope
        value = value / 1.3  # normalizar por la suma de armónicos
        value *= volume * env

        # Convertir a entero de 16 bits con signo
        sample = int(value * 32767)
        sample = max(-32768, min(32767, sample))
        samples.append(sample)

    # Escribir archivo WAV
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(output_path), "w") as wav_file:
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 16 bits
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    print(f"Sonido de notificación generado: {output_path}")
    print(f"  Duración: {duration_sec}s | Frecuencia: {frequency}Hz | "
          f"Muestras: {sample_rate}Hz | Canales: Mono | Bits: 16")


if __name__ == "__main__":
    sounds_dir = Path(__file__).resolve().parent.parent / "shared" / "sounds"
    output = str(sounds_dir / "notify.wav")
    generate_notify_wav(output)
    print("Hecho.")
