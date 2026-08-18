# Plandex on Android/Termux

This experiment validates PocketPort against `plandex-ai/plandex` as a second, architecturally different real-world target after DeepSeek Harness.

## Result

**Status: the official Plandex 2.2.1 Linux ARM64 CLI binary runs on Android/Termux through `pocketport run`.**

The final validated command was:

```bash
cd ~/pp-plandex-cli
pocketport run -- ./plandex version
```

and returned:

```text
[PocketPort] Termux runtime compatibility enabled
2.2.1
```

No Plandex source patch was required.

## Why this case matters

Plandex is structurally different from DeepSeek Harness:

- the CLI is written in Go and distributed as a Linux ARM64 release binary
- local self-hosting uses a client/server architecture
- the local server stack uses Docker Compose and PostgreSQL
- the repository therefore contains both a potentially native CLI surface and a container-oriented service surface

That exposed two new PocketPort requirements:

1. external Linux binaries may be executable on Android but still assume conventional Linux filesystem locations for DNS and CA certificates
2. one repository-level `native` / `hybrid` / `proot` label is too coarse for multi-component projects

## Initial PocketPort scan

The first scan on the real phone reported:

```text
PocketPort score: 53/100
Strategy: hybrid
Stack: docker-compose, go, docker
```

The important high-severity finding was Docker Compose. This was directionally correct for Plandex local self-hosting, but too coarse for the repository as a whole because the CLI is a separate Go executable.

## Official ARM64 binary test

The official Plandex 2.2.1 Linux ARM64 release was downloaded and executed directly in Termux.

The binary started successfully, proving that Android could execute this particular release binary and that there was no immediate architecture or dynamic-loader blocker on the tested host.

It then failed during Go package initialization while downloading a tokenizer resource:

```text
panic: error getting encoding for model:
Get "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken":
dial tcp: lookup openaipublic.blob.core.windows.net on [::1]:53:
read udp [::1]:...->[::1]:53: read: connection refused
```

## Runtime blocker 1: Linux DNS path assumption

The tested Termux environment had:

```text
/etc/resolv.conf                 empty / unavailable to the Linux binary
$PREFIX/etc/resolv.conf         nameserver 8.8.8.8
                                nameserver 8.8.4.4
```

A direct Termux `curl` request to the same Azure Blob URL returned HTTP 200, proving that general network connectivity was working.

Binding the Termux resolver file over `/etc/resolv.conf` with PRoot moved execution past DNS resolution:

```bash
proot -b "$PREFIX/etc/resolv.conf:/etc/resolv.conf" ./plandex version
```

## Runtime blocker 2: Linux CA bundle path assumption

After DNS was fixed, the next failure was:

```text
tls: failed to verify certificate: x509: certificate signed by unknown authority
```

Using the Termux CA bundle explicitly solved the TLS failure:

```bash
SSL_CERT_FILE="$PREFIX/etc/tls/cert.pem" \
  proot -b "$PREFIX/etc/resolv.conf:/etc/resolv.conf" \
  ./plandex version
```

Result:

```text
2.2.1
```

## PocketPort runtime fix

PocketPort now detects external ELF executables launched from Termux and, when the relevant Termux files exist:

- sets `SSL_CERT_FILE=$PREFIX/etc/tls/cert.pem`
- uses PRoot only as a lightweight file overlay for `$PREFIX/etc/resolv.conf -> /etc/resolv.conf`

This is deliberately not a full Linux distribution fallback. The application still executes as the downloaded binary; PRoot is only supplying a conventional Linux path for the resolver file.

Termux-native ELF executables under `$PREFIX` are left alone so PocketPort does not wrap its own toolchain unnecessarily.

## Component-aware scanner feedback

This case also motivated component-level assessments. A repository can legitimately contain surfaces with different Android strategies, for example:

```text
CLI / client           native candidate
server source          native/build-dependent candidate
local service stack    hybrid because Docker Compose is required
```

PocketPort now derives component hints for common surfaces such as `cli`, `client`, `server`, `api`, `backend`, `worker`, `web`, and Docker Compose service stacks. The repository-level strategy remains useful as a conservative summary, while the component view explains which part actually causes the adaptation requirement.

## What is not validated

This experiment does **not** prove that Plandex local self-host mode is fully operational inside stock Termux.

The official local mode uses Docker Compose and PostgreSQL, so backend hosting remains a separate compatibility problem. The validated result is narrower and useful:

- official Linux ARM64 CLI binary starts on Android
- DNS compatibility is repaired by PocketPort
- TLS trust compatibility is repaired by PocketPort
- `pocketport run -- ./plandex version` works without manual environment variables or bind arguments

That is enough to establish a second reusable PocketPort runtime compatibility pattern without claiming the entire Plandex deployment is Android-native.
