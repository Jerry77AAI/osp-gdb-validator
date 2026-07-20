# Clean-Room Provenance Statement

**Repo:** osp-gdb-validator
**Author:** Jerry Stevens — Director Engineering · AI Engineer · OSP Veteran (30 yrs)
**Built with:** Claude (AI engineering partner)
**Date:** 2026-07-20

## What this document is

Before writing the first line of code, we documented what this project may and
may not contain. Deciding what stays *out* of a public repo is an engineering
discipline in its own right, and this file is the record of that decision.

## Provenance rules applied to every artifact in this repo

1. **All code is original**, written from scratch for this repo in July 2026.
2. **All schema content is synthetic.** The FTTx demo schema and sample
   geodatabases were invented for this project. Feature classes, field names,
   domains, IDs, and coordinates are fabricated; coordinates fall in an
   unpopulated demo grid. No real network, customer, or project data exists
   anywhere in this repo.
3. **Industry standards are the only external inputs.** Public, citable
   sources only — e.g. TIA-598 fiber color conventions, common Esri file
   geodatabase concepts (fields, coded/range domains, feature classes) as
   documented publicly by Esri and the GDAL project.
4. **No former-employer material.** Nothing in this repo derives from,
   reconstructs, or references any prior employer's schemas, standards,
   client data, work product, or internal documents. This repo was built
   under a standing clean-room policy with automated checks that scan for
   disallowed terms before any publish.
5. **Tooling is fully open-source:** GDAL/OGR (OpenFileGDB driver), Python,
   PyYAML, pytest, GitHub Actions. No proprietary licenses are required to
   build, test, or run anything here.

## What was deliberately excluded

- Real-world schemas from any employer or client engagement — even
  "sanitized" versions. Sanitization is not clean-room; synthesis is.
- Real pole, cable, splice, or address data of any kind.
- Any pricing, costing, or financial modeling logic tied to real projects.

## The test we applied

> "If a lawyer for any past employer read every file in this repo, is there
> anything they could point to as theirs?"

The answer must be an unambiguous **no** before any commit is pushed.
