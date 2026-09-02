import os
import sys
import argparse
import time

try:
    import torch
    from transformers import pipeline
except ImportError:
    print("XATO: 'transformers' yoki 'torch' o'rnatilmagan.")
    print("Iltimos o'rnating: pip install transformers torch torchaudio accelerate")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Test VibeVoice-ASR with a local audio file.")
    parser.add_argument("audio_path", help="Path to the .wav or .ogg audio file")
    args = parser.parse_args()

    if not os.path.exists(args.audio_path):
        print(f"Xato: Fayl topilmadi: {args.audio_path}")
        sys.exit(1)

    print(f"=== VibeVoice-ASR Test ({args.audio_path}) ===")
    
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    
    print(f"[*] Qurilma (Device): {device}")
    print(f"[*] Precision: {torch_dtype}")
    
    if device == "cpu":
        print("[!] OGOHLANTIRISH: Model CPU da ishlamoqda. 7B model uchun bu O'TA SEKIN bo'lishi mumkin!")

    print("[*] Model yuklanmoqda: microsoft/VibeVoice-ASR-HF ...")
    start_time = time.time()
    
    try:
        asr_pipeline = pipeline(
            "automatic-speech-recognition", 
            model="microsoft/VibeVoice-ASR-HF",
            device=device,
            torch_dtype=torch_dtype
        )
    except Exception as e:
        print(f"[XATO] Modelni yuklashda muammo: {e}")
        sys.exit(1)
        
    print(f"[+] Model yuklandi! ({time.time() - start_time:.2f} soniya)")
    
    print("[*] Audio qayta ishlanmoqda (STT + Timestamps + Speaker)...")
    start_time = time.time()
    
    result = asr_pipeline(
        args.audio_path,
        return_timestamps=True,
    )
    
    end_time = time.time()
    print(f"[+] Qayta ishlash tugadi! ({end_time - start_time:.2f} soniya)")
    print("\n--- NATIJA ---")
    print(result.get("text", result))
    print("--------------\n")

if __name__ == "__main__":
    main()
