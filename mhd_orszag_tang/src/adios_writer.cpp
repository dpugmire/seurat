#include "adios_writer.hpp"

#include <stdexcept>

namespace ot {

#ifdef OT_USE_MPI
AdiosWriter::AdiosWriter(const SimulationParams& params,
                         int global_nx,
                         int global_ny,
                         int local_ny,
                         int y_offset,
                         int rank,
                         MPI_Comm comm)
    : rank_(rank), adios_(comm), io_(adios_.DeclareIO("ot_io")) {
#else
AdiosWriter::AdiosWriter(const SimulationParams& params,
                         int global_nx,
                         int global_ny,
                         int local_ny,
                         int y_offset,
                         int rank)
    : rank_(rank), adios_(), io_(adios_.DeclareIO("ot_io")) {
#endif
  io_.SetEngine(params.adios_engine);

  const adios2::Dims shape = {static_cast<std::size_t>(global_ny), static_cast<std::size_t>(global_nx)};
  const adios2::Dims start = {static_cast<std::size_t>(y_offset), 0};
  const adios2::Dims count = {static_cast<std::size_t>(local_ny), static_cast<std::size_t>(global_nx)};

  rho_ = io_.DefineVariable<double>("rho", shape, start, count);
  pressure_ = io_.DefineVariable<double>("pressure", shape, start, count);
  vx_ = io_.DefineVariable<double>("vx", shape, start, count);
  vy_ = io_.DefineVariable<double>("vy", shape, start, count);
  vz_ = io_.DefineVariable<double>("vz", shape, start, count);
  bx_ = io_.DefineVariable<double>("bx", shape, start, count);
  by_ = io_.DefineVariable<double>("by", shape, start, count);
  bz_ = io_.DefineVariable<double>("bz", shape, start, count);
  speed_ = io_.DefineVariable<double>("speed", shape, start, count);
  current_z_ = io_.DefineVariable<double>("current_z", shape, start, count);

  step_ = io_.DefineVariable<int>("step");
  time_ = io_.DefineVariable<double>("time");
  mass_ = io_.DefineVariable<double>("mass");
  kinetic_energy_ = io_.DefineVariable<double>("kinetic_energy");
  magnetic_energy_ = io_.DefineVariable<double>("magnetic_energy");
  internal_energy_ = io_.DefineVariable<double>("internal_energy");
  total_energy_ = io_.DefineVariable<double>("total_energy");
  mean_pressure_ = io_.DefineVariable<double>("mean_pressure");
  max_speed_ = io_.DefineVariable<double>("max_speed");
  current_abs_max_ = io_.DefineVariable<double>("current_abs_max");
  current_rms_ = io_.DefineVariable<double>("current_rms");
  divb_abs_max_ = io_.DefineVariable<double>("divb_abs_max");
  divb_l2_ = io_.DefineVariable<double>("divb_l2");

  engine_ = io_.Open(params.output_file, adios2::Mode::Write);
}

AdiosWriter::~AdiosWriter() {
  close();
}

void AdiosWriter::write(int step,
                        double time,
                        const OutputFields& fields,
                        const ScalarDiagnostics& diagnostics) {
  if (closed_) {
    throw std::runtime_error("ADIOS writer is closed");
  }

  engine_.BeginStep();
  engine_.Put(rho_, fields.rho.data());
  engine_.Put(pressure_, fields.pressure.data());
  engine_.Put(vx_, fields.vx.data());
  engine_.Put(vy_, fields.vy.data());
  engine_.Put(vz_, fields.vz.data());
  engine_.Put(bx_, fields.bx.data());
  engine_.Put(by_, fields.by.data());
  engine_.Put(bz_, fields.bz.data());
  engine_.Put(speed_, fields.speed.data());
  engine_.Put(current_z_, fields.current_z.data());

  if (rank_ == 0) {
    engine_.Put(step_, step);
    engine_.Put(time_, time);
    engine_.Put(mass_, diagnostics.mass);
    engine_.Put(kinetic_energy_, diagnostics.kinetic_energy);
    engine_.Put(magnetic_energy_, diagnostics.magnetic_energy);
    engine_.Put(internal_energy_, diagnostics.internal_energy);
    engine_.Put(total_energy_, diagnostics.total_energy);
    engine_.Put(mean_pressure_, diagnostics.mean_pressure);
    engine_.Put(max_speed_, diagnostics.max_speed);
    engine_.Put(current_abs_max_, diagnostics.current_abs_max);
    engine_.Put(current_rms_, diagnostics.current_rms);
    engine_.Put(divb_abs_max_, diagnostics.divb_abs_max);
    engine_.Put(divb_l2_, diagnostics.divb_l2);
  }

  engine_.EndStep();
}

void AdiosWriter::close() {
  if (!closed_) {
    engine_.Close();
    closed_ = true;
  }
}

}  // namespace ot
