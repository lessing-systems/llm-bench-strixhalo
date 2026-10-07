# Winner (2026-10-06): halogen-flash-server 0.16.2 serving Swift-1.5 Qwen3.8-Flash-Next IQ4_XS
# (UkisAI's standard GGUF, repacked losslessly at start by halogen's bring-your-own-GGUF path),
# with halogen's own MTP draft head and tokenizer. Measured in results/strix-halo-395/REPORT.md.
#
# The engine is used unmodified; this image only pins it by digest and bakes the benchmarked configuration in
# as defaults, so the setup stays reproducible if the upstream tag changes. Weights are NOT in the image: mount them
# read-only (see docker-compose.yml).
#
# Build + push:
#   sudo docker build -t local/halogen-swift:0.16.2-swift1.5-iq4xs .
#   sudo docker push <your-registry>/halogen-swift:0.16.2-swift1.5-iq4xs   # optional
FROM ghcr.io/peonist-ai/halogen-flash-server:0.16.2@sha256:0c61bf84ac22308a53f5d1ca6b86806702d7039e5ebc51cae4c66621b92fe04a

LABEL org.opencontainers.image.title="halogen-swift" \
      org.opencontainers.image.description="halogen-flash-server 0.16.2 + Swift-1.5 Qwen3.8-Flash-Next IQ4_XS GGUF, 128k context, 1 KV slot" \
      org.opencontainers.image.base.name="ghcr.io/peonist-ai/halogen-flash-server:0.16.2" \
      org.opencontainers.image.base.digest="sha256:0c61bf84ac22308a53f5d1ca6b86806702d7039e5ebc51cae4c66621b92fe04a" \
      bench.model="ukisai/Swift-1.5-Qwen3.8-Flash-Next-GGUF IQ4_XS (3 shards, 97.7 GB, Swift Open License v1.0)" \
      bench.weights_mounts="/gguf: Swift GGUF dir (ro); /models: halogen weights dir for qwen38-flash-next-mtp.hgn + tokenizer/ (ro)"

# Same engine settings as the stock 0.15.0 docker-compose.yml, plus the GGUF trunk and head.
# A value set in docker-compose.yml still overrides these. HALOGEN_TOKENIZER is needed because the api service sees
# HALOGEN_CHECKPOINT too and would otherwise look for tokenizer/ beside the GGUF (found by the smoke test).
ENV HALOGEN_CHECKPOINT=/gguf/IQ4_XS/Swift-1.5-Qwen3.8-Flash-Next-IQ4_XS-00001-of-00003.gguf \
    HALOGEN_MTP_HEAD=/models/qwen38-flash-next-mtp.hgn \
    HALOGEN_TOKENIZER=/models/tokenizer \
    HALOGEN_CTX=131072 \
    HALOGEN_KV_POOL_POSITIONS=131072 \
    HALOGEN_KV_SLOTS=1 \
    HALOGEN_MAX_TOK=16384 \
    HALOGEN_HOST_RESERVE_GIB=28 \
    HALOGEN_CACHE_BRANCHES=3 \
    HALOGEN_MAX_TOKENS_DEFAULT=8192 \
    HALOGEN_MAX_TOKENS_CAP=16384 \
    HALOGEN_PROMPT_CACHE=2 \
    HALOGEN_COMPOSABLE_CONTEXT=0 \
    HALOGEN_WEIGHTS_LOCK=1 \
    HALOGEN_ENGINE_WATCHDOG_S=0 \
    HALOGEN_VERBOSE=1
