#include "adios_writer.hpp"
#include "mhd2d.hpp"

#include <cmath>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

#ifdef OT_USE_MPI
#include <mpi.h>
#endif

namespace {

void print_usage(const char* prog) {
  std::cout << "Usage: " << prog << " [options]\n\n"
            << "Core options:\n"
            << "  --nx <int>                    Global x resolution (default 256)\n"
            << "  --ny <int>                    Global y resolution (default 256)\n"
            << "  --tfinal <float>              Final simulation time (default 1.0)\n"
            << "  --cfl <float>                 CFL number (default 0.35)\n"
            << "  --gamma <float>               Ratio of specific heats (default 5/3)\n"
            << "  --solver <name>               rusanov|hll|muscl_hll|muscl_rusanov\n"
            << "  --flux <name>                 rusanov|hll (optional override)\n"
            << "  --reconstruction <name>       first|muscl (optional override)\n"
            << "\nOutput options:\n"
            << "  --output <path>               ADIOS2 BP output file (default output/orszag_tang.bp)\n"
            << "  --engine <name>               ADIOS2 engine (default BP5)\n"
            << "  --output-every-steps <int>    Save every N steps (0 disables)\n"
            << "  --output-every-time <float>   Save every Dt in sim time (0 disables)\n"
            << "  --save-initial                Save initial state (default true)\n"
            << "  --no-save-initial             Skip initial output\n"
            << "\nStability / control options:\n"
            << "  --rho-floor <float>           Density floor\n"
            << "  --p-floor <float>             Pressure floor\n"
            << "  --glm-ch <float>              GLM propagation speed\n"
            << "  --glm-damping <float>         GLM damping coefficient\n"
            << "  --max-steps <int>             Hard step limit\n"
            << "  --log-every-steps <int>       Print progress every N steps\n"
            << "  --help                        Show this help\n";
}

bool parse_int_arg(const std::string& arg, int& out) {
  try {
    out = std::stoi(arg);
    return true;
  } catch (...) {
    return false;
  }
}

bool parse_double_arg(const std::string& arg, double& out) {
  try {
    out = std::stod(arg);
    return true;
  } catch (...) {
    return false;
  }
}

std::string next_value(int& i, int argc, char** argv, const std::string& opt) {
  if (i + 1 >= argc) {
    throw std::runtime_error("Missing value for option " + opt);
  }
  ++i;
  return argv[i];
}

}  // namespace

int main(int argc, char** argv) {
#ifdef OT_USE_MPI
  MPI_Init(&argc, &argv);
  MPI_Comm comm = MPI_COMM_WORLD;
  int rank = 0;
  MPI_Comm_rank(comm, &rank);
#else
  int rank = 0;
#endif

  try {
    ot::SimulationParams params;

    for (int i = 1; i < argc; ++i) {
      const std::string arg = argv[i];

      if (arg == "--help") {
        if (rank == 0) {
          print_usage(argv[0]);
        }
#ifdef OT_USE_MPI
        MPI_Finalize();
#endif
        return 0;
      }
      if (arg == "--nx") {
        int v = 0;
        if (!parse_int_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid integer for --nx");
        }
        params.nx = v;
        continue;
      }
      if (arg == "--ny") {
        int v = 0;
        if (!parse_int_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid integer for --ny");
        }
        params.ny = v;
        continue;
      }
      if (arg == "--tfinal") {
        double v = 0.0;
        if (!parse_double_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid float for --tfinal");
        }
        params.tfinal = v;
        continue;
      }
      if (arg == "--cfl") {
        double v = 0.0;
        if (!parse_double_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid float for --cfl");
        }
        params.cfl = v;
        continue;
      }
      if (arg == "--gamma") {
        double v = 0.0;
        if (!parse_double_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid float for --gamma");
        }
        params.gamma = v;
        continue;
      }
      if (arg == "--solver") {
        const std::string solver_name = next_value(i, argc, argv, arg);
        if (!ot::parse_solver_name(solver_name, params.flux, params.reconstruction)) {
          throw std::runtime_error("Unknown solver: " + solver_name);
        }
        continue;
      }
      if (arg == "--flux") {
        const std::string flux_name = next_value(i, argc, argv, arg);
        if (flux_name == "rusanov") {
          params.flux = ot::FluxType::Rusanov;
        } else if (flux_name == "hll") {
          params.flux = ot::FluxType::HLL;
        } else {
          throw std::runtime_error("Unknown flux: " + flux_name);
        }
        continue;
      }
      if (arg == "--reconstruction") {
        const std::string recon_name = next_value(i, argc, argv, arg);
        if (recon_name == "first" || recon_name == "first_order") {
          params.reconstruction = ot::ReconstructionType::FirstOrder;
        } else if (recon_name == "muscl") {
          params.reconstruction = ot::ReconstructionType::MUSCL;
        } else {
          throw std::runtime_error("Unknown reconstruction: " + recon_name);
        }
        continue;
      }
      if (arg == "--output") {
        params.output_file = next_value(i, argc, argv, arg);
        continue;
      }
      if (arg == "--engine") {
        params.adios_engine = next_value(i, argc, argv, arg);
        continue;
      }
      if (arg == "--output-every-steps") {
        int v = 0;
        if (!parse_int_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid integer for --output-every-steps");
        }
        params.output_every_steps = v;
        continue;
      }
      if (arg == "--output-every-time") {
        double v = 0.0;
        if (!parse_double_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid float for --output-every-time");
        }
        params.output_every_time = v;
        continue;
      }
      if (arg == "--save-initial") {
        params.save_initial = true;
        continue;
      }
      if (arg == "--no-save-initial") {
        params.save_initial = false;
        continue;
      }
      if (arg == "--rho-floor") {
        double v = 0.0;
        if (!parse_double_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid float for --rho-floor");
        }
        params.rho_floor = v;
        continue;
      }
      if (arg == "--p-floor") {
        double v = 0.0;
        if (!parse_double_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid float for --p-floor");
        }
        params.p_floor = v;
        continue;
      }
      if (arg == "--glm-ch") {
        double v = 0.0;
        if (!parse_double_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid float for --glm-ch");
        }
        params.glm_ch = v;
        continue;
      }
      if (arg == "--glm-damping") {
        double v = 0.0;
        if (!parse_double_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid float for --glm-damping");
        }
        params.glm_damping = v;
        continue;
      }
      if (arg == "--max-steps") {
        int v = 0;
        if (!parse_int_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid integer for --max-steps");
        }
        params.max_steps = v;
        continue;
      }
      if (arg == "--log-every-steps") {
        int v = 0;
        if (!parse_int_arg(next_value(i, argc, argv, arg), v)) {
          throw std::runtime_error("Invalid integer for --log-every-steps");
        }
        params.log_every_steps = v;
        continue;
      }

      throw std::runtime_error("Unknown option: " + arg);
    }

    if (params.nx <= 4 || params.ny <= 4) {
      throw std::runtime_error("nx and ny must be > 4");
    }
    if (params.cfl <= 0.0) {
      throw std::runtime_error("cfl must be > 0");
    }
    if (params.tfinal <= 0.0) {
      throw std::runtime_error("tfinal must be > 0");
    }
    if (params.output_every_steps < 0 || params.output_every_time < 0.0) {
      throw std::runtime_error("output cadence values must be non-negative");
    }

    const std::filesystem::path output_path(params.output_file);
    if (rank == 0 && output_path.has_parent_path()) {
      std::filesystem::create_directories(output_path.parent_path());
    }
#ifdef OT_USE_MPI
    MPI_Barrier(comm);
#endif

#ifdef OT_USE_MPI
    ot::MHD2D sim(params, comm);
#else
    ot::MHD2D sim(params);
#endif
    sim.initialize_orszag_tang();

#ifdef OT_USE_MPI
    ot::AdiosWriter writer(params,
                           sim.global_nx(),
                           sim.global_ny(),
                           sim.local_ny(),
                           sim.y_offset(),
                           sim.rank(),
                           comm);
#else
    ot::AdiosWriter writer(params,
                           sim.global_nx(),
                           sim.global_ny(),
                           sim.local_ny(),
                           sim.y_offset(),
                           sim.rank());
#endif

    if (rank == 0) {
      std::cout << std::setprecision(6) << std::fixed;
      std::cout << "Running Orszag-Tang MHD\n"
                << "  Grid: " << params.nx << " x " << params.ny << "\n"
                << "  Solver: " << ot::reconstruction_to_string(params.reconstruction)
                << "+" << ot::flux_to_string(params.flux) << "\n"
                << "  tfinal: " << params.tfinal << ", CFL: " << params.cfl << "\n"
                << "  Output: " << params.output_file << " (" << params.adios_engine << ")\n";
    }

    double t = 0.0;
    int step = 0;

    if (params.save_initial) {
      ot::OutputFields fields;
      ot::ScalarDiagnostics diagnostics;
      sim.extract_output(fields);
      sim.compute_diagnostics(diagnostics);
      writer.write(step, t, fields, diagnostics);
    }

    const double no_time_cadence = std::numeric_limits<double>::infinity();
    double next_time_dump = params.output_every_time > 0.0 ? params.output_every_time : no_time_cadence;

    while (t < params.tfinal && step < params.max_steps) {
      double dt = sim.compute_time_step();
      if (!std::isfinite(dt) || dt <= 0.0) {
        throw std::runtime_error("Non-finite or non-positive dt computed");
      }
      if (t + dt > params.tfinal) {
        dt = params.tfinal - t;
      }

      sim.advance(dt);
      t += dt;
      ++step;

      const bool due_step = (params.output_every_steps > 0) && (step % params.output_every_steps == 0);
      bool due_time = false;
      if (params.output_every_time > 0.0 && t + 1.0e-14 >= next_time_dump) {
        due_time = true;
        while (t + 1.0e-14 >= next_time_dump) {
          next_time_dump += params.output_every_time;
        }
      }

      const bool final_dump = (t + 1.0e-14 >= params.tfinal);
      if (due_step || due_time || final_dump) {
        ot::OutputFields fields;
        ot::ScalarDiagnostics diagnostics;
        sim.extract_output(fields);
        sim.compute_diagnostics(diagnostics);
        writer.write(step, t, fields, diagnostics);
      }

      if (rank == 0 && params.log_every_steps > 0 && step % params.log_every_steps == 0) {
        std::cout << "step=" << step << " t=" << t << " dt=" << dt << "\n";
      }
    }

    if (rank == 0) {
      std::cout << "Completed: steps=" << step << " t=" << t << "\n";
      if (step >= params.max_steps && t < params.tfinal) {
        std::cout << "Stopped at max_steps before tfinal\n";
      }
    }

    writer.close();

#ifdef OT_USE_MPI
    MPI_Finalize();
#endif
    return 0;

  } catch (const std::exception& ex) {
    std::cerr << "Error: " << ex.what() << "\n";
#ifdef OT_USE_MPI
    MPI_Finalize();
#endif
    return 1;
  }
}
