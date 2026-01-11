{{/*
Expand the name of the chart.
*/}}
{{- define "ai-sre-agent.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ai-sre-agent.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label
*/}}
{{- define "ai-sre-agent.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ai-sre-agent.labels" -}}
helm.sh/chart: {{ include "ai-sre-agent.chart" . }}
{{ include "ai-sre-agent.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ai-sre-agent.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ai-sre-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Service account name
*/}}
{{- define "ai-sre-agent.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ai-sre-agent.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Secret name
*/}}
{{- define "ai-sre-agent.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- include "ai-sre-agent.fullname" . }}-secrets
{{- end }}
{{- end }}

{{/*
Redis URL
*/}}
{{- define "ai-sre-agent.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- if .Values.redis.auth.enabled }}
redis://:{{ .Values.redis.auth.password | default "$(REDIS_PASSWORD)" }}@{{ include "ai-sre-agent.fullname" . }}-redis-master:6379/0
{{- else }}
redis://{{ include "ai-sre-agent.fullname" . }}-redis-master:6379/0
{{- end }}
{{- else if .Values.externalRedis.url }}
{{- .Values.externalRedis.url }}
{{- else }}
redis://:$(REDIS_PASSWORD)@{{ .Values.externalRedis.host }}:{{ .Values.externalRedis.port }}/0
{{- end }}
{{- end }}

{{/*
PostgreSQL URL
*/}}
{{- define "ai-sre-agent.postgresqlUrl" -}}
{{- if .Values.postgresql.enabled }}
postgresql://{{ .Values.postgresql.auth.username }}:$(DATABASE_PASSWORD)@{{ include "ai-sre-agent.fullname" . }}-postgresql:5432/{{ .Values.postgresql.auth.database }}
{{- else if .Values.externalPostgresql.url }}
{{- .Values.externalPostgresql.url }}
{{- else }}
postgresql://{{ .Values.externalPostgresql.username }}:$(DATABASE_PASSWORD)@{{ .Values.externalPostgresql.host }}:{{ .Values.externalPostgresql.port }}/{{ .Values.externalPostgresql.database }}
{{- end }}
{{- end }}

{{/*
Image with registry
*/}}
{{- define "ai-sre-agent.image" -}}
{{- $registry := .global.imageRegistry | default "" }}
{{- $repo := .image.repository }}
{{- $tag := .image.tag | default "latest" }}
{{- if $registry }}
{{- printf "%s/%s:%s" $registry $repo $tag }}
{{- else }}
{{- printf "%s:%s" $repo $tag }}
{{- end }}
{{- end }}
