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
Create chart name and version as used by the chart label.
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
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
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
Create the name of the service account to use
*/}}
{{- define "ai-sre-agent.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ai-sre-agent.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the secret to use
*/}}
{{- define "ai-sre-agent.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- include "ai-sre-agent.fullname" . }}-secrets
{{- end }}
{{- end }}

{{/*
Image name with registry
*/}}
{{- define "ai-sre-agent.image" -}}
{{- $registry := .Values.global.imageRegistry | default "" }}
{{- $repository := .image.repository }}
{{- $tag := .image.tag | default "latest" }}
{{- if $registry }}
{{- printf "%s/%s:%s" $registry $repository $tag }}
{{- else }}
{{- printf "%s:%s" $repository $tag }}
{{- end }}
{{- end }}

{{/*
MCP Server labels
*/}}
{{- define "ai-sre-agent.mcpLabels" -}}
helm.sh/chart: {{ include "ai-sre-agent.chart" .context }}
app.kubernetes.io/name: {{ include "ai-sre-agent.name" .context }}-mcp-{{ .name }}
app.kubernetes.io/instance: {{ .context.Release.Name }}
app.kubernetes.io/component: mcp-server
app.kubernetes.io/part-of: {{ include "ai-sre-agent.name" .context }}
{{- if .context.Chart.AppVersion }}
app.kubernetes.io/version: {{ .context.Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .context.Release.Service }}
{{- end }}

{{/*
MCP Server selector labels
*/}}
{{- define "ai-sre-agent.mcpSelectorLabels" -}}
app.kubernetes.io/name: {{ include "ai-sre-agent.name" .context }}-mcp-{{ .name }}
app.kubernetes.io/instance: {{ .context.Release.Name }}
{{- end }}
