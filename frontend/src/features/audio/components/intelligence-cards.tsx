"use client";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { formatConfidence, formatEnumLabel } from "@/lib/format";

import { useAudioAcoustic, useAudioSpeech, useAudioTechnical } from "../api";
import { FieldRow, SectionBody, SectionCard } from "./section";

const HIDDEN_KEYS = new Set([
  "audio_id",
  "technical_completed",
  "acoustic_completed",
  "speech_completed",
  "technical_version",
  "acoustic_version",
  "speech_version",
]);

function extraNumericFields(
  data: Record<string, unknown>,
  knownKeys: string[],
): Array<{ label: string; value: number }> {
  const known = new Set([...knownKeys, ...HIDDEN_KEYS]);
  return Object.entries(data)
    .filter(
      ([key, value]) =>
        !known.has(key) && typeof value === "number" && Number.isFinite(value),
    )
    .map(([key, value]) => ({
      label: formatEnumLabel(key),
      value: value as number,
    }));
}

function ScoringDetails({
  version,
  fields,
}: {
  version: string | null;
  fields: Array<{ label: string; value: number }>;
}) {
  return (
    <details className="group mt-2 rounded-md border border-border bg-muted/30 px-3 py-2">
      <summary className="cursor-pointer select-none text-xs text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-open:mb-2">
        Scoring details
      </summary>
      <dl>
        <FieldRow label="Model version" value={version ?? "—"} mono />
        {fields.length > 0 ? (
          fields.map((field) => (
            <FieldRow
              key={field.label}
              label={field.label}
              value={formatConfidence(field.value)}
              mono
            />
          ))
        ) : (
          <p className="py-1 text-xs text-muted-foreground">
            No additional scoring values were recorded.
          </p>
        )}
      </dl>
    </details>
  );
}

function YesNoBadge({ value }: { value: boolean }) {
  return (
    <Badge variant={value ? "default" : "muted"}>{value ? "Yes" : "No"}</Badge>
  );
}

export function TechnicalIntelligenceCard({ audioId }: { audioId: string }) {
  const query = useAudioTechnical(audioId);
  return (
    <SectionCard
      title="Technical Intelligence"
      description="Signal quality and conversation integrity"
    >
      <SectionBody query={query} pendingLabel="Technical analysis">
        {(data) => (
          <>
            <dl>
              <FieldRow
                label="Audio quality"
                value={
                  <Badge variant="outline">
                    {formatEnumLabel(String(data.audio_quality))}
                  </Badge>
                }
              />
              <FieldRow
                label="Speaker overlap"
                value={<YesNoBadge value={data.speaker_overlap_present} />}
              />
              <FieldRow
                label="Long silence"
                value={<YesNoBadge value={data.long_silence_present} />}
              />
            </dl>
            <ScoringDetails
              version={data.technical_version}
              fields={extraNumericFields(data as unknown as Record<string, unknown>, [
                "audio_quality",
                "speaker_overlap_present",
                "long_silence_present",
              ])}
            />
          </>
        )}
      </SectionBody>
    </SectionCard>
  );
}

export function AcousticIntelligenceCard({ audioId }: { audioId: string }) {
  const query = useAudioAcoustic(audioId);
  return (
    <SectionCard
      title="Acoustic Intelligence"
      description="Background noise detection"
    >
      <SectionBody query={query} pendingLabel="Acoustic analysis">
        {(data) => (
          <>
            <dl>
              <FieldRow
                label="Noise present"
                value={<YesNoBadge value={data.background_noise_present} />}
              />
              <FieldRow
                label="Noise type"
                value={
                  <Badge variant="outline">
                    {formatEnumLabel(String(data.background_noise_type))}
                  </Badge>
                }
              />
              <FieldRow
                label="Noise severity"
                value={
                  <Badge variant="outline">
                    {formatEnumLabel(String(data.background_noise_severity))}
                  </Badge>
                }
              />
            </dl>
            <ScoringDetails
              version={data.acoustic_version}
              fields={extraNumericFields(data as unknown as Record<string, unknown>, [
                "background_noise_present",
                "background_noise_type",
                "background_noise_severity",
              ])}
            />
          </>
        )}
      </SectionBody>
    </SectionCard>
  );
}

function ProbabilityBars({ data }: { data: Record<string, unknown> }) {
  const raw = data.probabilities ?? data.top_probabilities;
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return null;
  const entries = Object.entries(raw as Record<string, unknown>)
    .filter(
      (entry): entry is [string, number] =>
        typeof entry[1] === "number" && Number.isFinite(entry[1]),
    )
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  if (entries.length === 0) return null;
  return (
    <div className="mt-3 space-y-2">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        Top probabilities
      </p>
      {entries.map(([label, value]) => (
        <div key={label} className="space-y-1">
          <div className="flex items-baseline justify-between text-xs">
            <span className="text-foreground">{formatEnumLabel(label)}</span>
            <span className="font-mono tabular-nums text-muted-foreground">
              {formatConfidence(value)}
            </span>
          </div>
          <Progress value={Math.round(value * 100)} aria-label={`${label} probability`} />
        </div>
      ))}
    </div>
  );
}

export function SpeechIntelligenceCard({ audioId }: { audioId: string }) {
  const query = useAudioSpeech(audioId);
  return (
    <SectionCard
      title="Speech Intelligence"
      description="Emotion recognition from speech"
    >
      <SectionBody query={query} pendingLabel="Speech analysis">
        {(data) => {
          const record = data as unknown as Record<string, unknown>;
          const confidence =
            typeof record.speech_confidence === "number"
              ? (record.speech_confidence as number)
              : null;
          return (
            <>
              <dl>
                <FieldRow
                  label="Emotion"
                  value={
                    <Badge variant="outline">
                      {formatEnumLabel(String(data.emotional_tone))}
                    </Badge>
                  }
                />
                <FieldRow
                  label="Emotion intensity"
                  value={
                    <Badge variant="outline">
                      {formatEnumLabel(String(data.emotional_intensity))}
                    </Badge>
                  }
                />
                {confidence !== null ? (
                  <FieldRow
                    label="Speech confidence"
                    value={formatConfidence(confidence)}
                    mono
                  />
                ) : null}
              </dl>
              <ProbabilityBars data={record} />
              <ScoringDetails
                version={data.speech_version}
                fields={extraNumericFields(record, [
                  "emotional_tone",
                  "emotional_intensity",
                  "probabilities",
                  "top_probabilities",
                  "speech_confidence",
                ])}
              />
            </>
          );
        }}
      </SectionBody>
    </SectionCard>
  );
}
