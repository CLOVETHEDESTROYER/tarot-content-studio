param([string]$InputFile, [string]$OutputFile, [string]$TimingFile)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
Add-Type -ReferencedAssemblies System.Speech -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Speech.Synthesis;
using System.Speech.AudioFormat;
public class SpeechMark {
    public int position;
    public int length;
    public double start;
    public string text;
}
public class StudioSpeech {
    public static List<SpeechMark> Render(string text, string path) {
        var marks = new List<SpeechMark>();
        using (var speaker = new SpeechSynthesizer()) {
            speaker.Rate = 0;
            foreach (var voice in speaker.GetInstalledVoices()) {
                if (voice.Enabled && voice.VoiceInfo.Culture.Name.StartsWith("en") && voice.VoiceInfo.Gender == VoiceGender.Female) {
                    speaker.SelectVoice(voice.VoiceInfo.Name); break;
                }
            }
            speaker.SpeakProgress += (s, e) => marks.Add(new SpeechMark {
                position = e.CharacterPosition, length = e.CharacterCount,
                start = e.AudioPosition.TotalSeconds, text = e.Text
            });
            speaker.SetOutputToWaveFile(path, new SpeechAudioFormatInfo(16000, AudioBitsPerSample.Sixteen, AudioChannel.Mono));
            speaker.Speak(text);
        }
        return marks;
    }
}
'@
$speechText = [IO.File]::ReadAllText($InputFile, [Text.Encoding]::UTF8)
$marks = [StudioSpeech]::Render($speechText, $OutputFile)
ConvertTo-Json -InputObject @($marks.ToArray()) -Depth 4 | Set-Content -LiteralPath $TimingFile -Encoding UTF8
