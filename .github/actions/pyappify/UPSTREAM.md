Adapted from ok-oldking/pyappify-action at c5cc8fe5c9bd5c732969018694a2645474c48b7e.
License: GPL-3.0, included in LICENSE.txt.

Changes: run auditable source on Node 24; accept a versioned launcher asset;
verify its SHA-256; use Zlib for NSIS; prepare frontend assets for bundle-only
reuse; verify the packaged app version. The launcher compilation recipe stays
identical to upstream. Install locked dependencies with npm ci before use.
