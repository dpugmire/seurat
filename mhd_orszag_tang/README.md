# 2D Orszag-Tang MHD (C++/MPI/ADIOS2)

This subproject provides a 2D uniform-grid ideal-MHD solver for the Orszag-Tang vortex, with:

- Multiple solver variants (`hll`, `rusanov`, `muscl_hll`, `muscl_rusanov`)
- Optional MPI domain decomposition in `y`
- ADIOS2 output (`BP4`/`BP5` or any engine ADIOS2 supports)
- Controls for output cadence by step and/or simulation time
- A JSON-driven ensemble runner

## Physics outputs

Each output step writes these 2D fields to ADIOS:

- `rho`
- `pressure`
- `vx`, `vy`, `vz`
- `bx`, `by`, `bz`
- `speed`
- `current_z`
- Scalars per step on rank 0:
  - `step`, `time`
  - `mass`
  - `kinetic_energy`, `magnetic_energy`, `internal_energy`, `total_energy`
  - `mean_pressure`
  - `max_speed`
  - `current_abs_max`, `current_rms`
  - `divb_abs_max`, `divb_l2`

## Build

Requirements:

- CMake >= 3.18
- C++17 compiler
- ADIOS2 with C++ bindings
- MPI (optional, enabled by default)

```bash
cd /Users/dpn/proj/campaign_viewer/campaign_viewer/catnip_db/mhd_orszag_tang
cmake -S . -B build -DOT_ENABLE_MPI=ON
cmake --build build -j
```

If you want serial-only build:

```bash
cmake -S . -B build -DOT_ENABLE_MPI=OFF
cmake --build build -j
```

## Run a single case

Serial:

```bash
./build/ot_mhd \
  --nx 512 --ny 512 \
  --solver muscl_hll \
  --tfinal 0.8 --cfl 0.3 \
  --output runs/ot_muscl.bp \
  --output-every-steps 20 \
  --output-every-time 0.05
```

MPI:

```bash
mpirun -n 2 ./build/ot_mhd \
  --nx 512 --ny 512 \
  --solver muscl_hll \
  --tfinal 0.8 --cfl 0.3 \
  --output runs/ot_muscl_mpi.bp \
  --output-every-steps 20 \
  --output-every-time 0.05
```

## Important controls

- `--solver`: `rusanov`, `hll`, `muscl_hll`, `muscl_rusanov`
- `--output-every-steps N`: dump every `N` steps (`0` disables)
- `--output-every-time dt`: dump every `dt` in simulation time (`0` disables)
- `--save-initial` / `--no-save-initial`
- `--glm-ch`, `--glm-damping` for divergence-cleaning behavior
- `--rho-floor`, `--p-floor` for positivity

## Run ensembles

Use the sample config and runner:

```bash
python3 scripts/run_ensemble.py --config ensembles/sample_ensemble.json
```

Dry-run to inspect commands:

```bash
python3 scripts/run_ensemble.py --config ensembles/sample_ensemble.json --dry-run
```

Run only selected members:

```bash
python3 scripts/run_ensemble.py --config ensembles/sample_ensemble.json --only muscl_hll hll_first_order
```

## Quick visualization

Create a PNG from any ADIOS output file:

```bash
python3 scripts/plot_snapshot.py --file runs/muscl_hll.bp --step -1 --out runs/muscl_hll_last.png
```

This plots `rho`, `pressure`, `current_z`, and `speed` in a 2x2 panel.
