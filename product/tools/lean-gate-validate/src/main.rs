//! P1-b validation: the fork's env-gated anti-tip rule, against the P0-2
//! corrected numbers (`product/brain-sim/analysis/p0_2_gate_probe.json`,
//! `product/calibration/lean-verify.md`).
//!
//! Run twice from this directory (README.md): once with no `LAMP_*` env
//! (V1 defaults), once with the b500 deployment env. The lean-geometry
//! checks run in both modes; the cog gate checks differ by mode, because
//! cog reads the environment once per process (`LazyLock`).

use lamp_body::cog;
use lamp_lean::{Angles, Geometry, Joint, Model};

/// rest0: yaw 0, shoulder -18, elbow 14, roll 0, pitch -45 degrees, in
/// bus order (servo IDs 1..5); counts = 2048 + rad/TAU*4096.
const REST0: [f32; 5] = [2048.0, 1843.2, 2207.2889, 2048.0, 1536.0];
/// The idle recording's frame 1682 through the sim's affine joint map
/// (`p0_2_cog_fix.py` `setnorm`), in bus order.
const IDLE: [f32; 5] = [2122.636, 1700.721, 1046.853, 2184.070, 1906.076];
/// V1's lamp-4ace rest reading, from cog.rs's own test: 17.851 mm off axis.
const V1_REST: [f32; 5] = [2023.0, 2052.0, 2047.0, 2053.0, 1950.0];

const CALIB: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../../calibration");

fn near(got: f64, want: f64, tol: f64, what: &str) {
    assert!((got - want).abs() <= tol, "{what}: {got} vs {want} +/-{tol}");
    println!("ok  {what:<44} {got:8.3}  (want {want} +-{tol})");
}

fn radians(counts: [f32; 5]) -> [f64; 5] {
    counts.map(|c| (f64::from(c) - 2048.0) * std::f64::consts::TAU / 4096.0)
}

/// Off-axis and lean-back of `counts` on a lean model; lean-back with
/// base yaw at the geometry's zero, as `cog::lean_back_mm` does.
fn metrics(model: &Model, yaw_zero: f64, counts: [f32; 5]) -> (f64, f64) {
    let mut rad = radians(counts);
    let [x, y, _] = model.check_pose(Angles::new(rad).unwrap()).centre_of_mass_m;
    let off = (x * 1000.0).hypot(y * 1000.0);
    rad[0] = yaw_zero;
    let lb = -model.check_pose(Angles::new(rad).unwrap()).centre_of_mass_m[0] * 1000.0;
    (off, lb)
}

fn main() {
    let fork = std::env::var(cog::LEAN_JSON_ENV).is_ok();
    println!(
        "mode: {}",
        if fork {
            "fork (LAMP_LEAN_JSON set)"
        } else {
            "V1 defaults (no LAMP_* env)"
        }
    );

    // 1. Both lean JSONs, env-independent: rest0 / idle off-axis and
    //    lean-back against the corrected MuJoCo numbers (0.1 mm rounding
    //    in the probe; the JSONs' FK agrees to 0.0017 mm).
    for (file, rest_off, rest_lb, idle_off, idle_lb) in [
        ("lean-lelamp.json", 69.8, 61.6, 98.0, 90.2),
        ("lean-lelamp-ballast.json", 45.3, 40.0, 63.5, 58.5),
    ] {
        let path = format!("{CALIB}/{file}");
        let text = std::fs::read_to_string(&path).unwrap();
        let geometry = Geometry::from_json(&text).unwrap();
        let yaw_zero = geometry
            .links
            .iter()
            .find(|link| link.joint == Joint::BaseYaw)
            .map_or(0.0, |link| link.angle_zero_rad);
        let model = Model::new(geometry).unwrap();
        let (off, lb) = metrics(&model, yaw_zero, REST0);
        near(off, rest_off, 0.12, &format!("{file} rest0 off-axis"));
        near(lb, rest_lb, 0.12, &format!("{file} rest0 lean-back"));
        let (off, lb) = metrics(&model, yaw_zero, IDLE);
        near(off, idle_off, 0.12, &format!("{file} idle off-axis"));
        near(lb, idle_lb, 0.12, &format!("{file} idle lean-back"));
    }

    // 2. The cog gates, by mode.
    if fork {
        near(cog::clip_mm(), 78.0, 0.0, "cog::clip_mm (LAMP_CLIP_MM=78)");
        near(cog::look_mm(), 72.0, 0.0, "cog::look_mm (LAMP_LOOK_MM=72)");
        assert!(cog::fold_bound_absolute(), "LAMP_FOLD_BOUND_MM=78 set");
        near(
            cog::fold_bound_mm(63.6),
            78.0,
            0.0,
            "absolute fold bound over relative 63.6",
        );
        near(cog::off_axis_mm(REST0), 45.3, 0.12, "cog rest0 off-axis (env JSON)");
        near(cog::lean_back_mm(REST0), 40.0, 0.12, "cog rest0 lean-back (env JSON)");
        near(cog::off_axis_mm(IDLE), 63.5, 0.12, "cog idle off-axis (env JSON)");
        near(cog::lean_back_mm(IDLE), 58.5, 0.12, "cog idle lean-back (env JSON)");
        // The idle->rest0 linear fold peaks at 74.9 mm off axis: inside
        // the absolute 78, outside the relative 63.6 that refused it.
        assert!(74.9 < cog::fold_bound_mm(63.6), "linear fold passes 78");
        assert!(74.9 > 63.6, "relative bound would refuse it");
    } else {
        near(cog::clip_mm(), 22.0, 0.0, "cog::clip_mm default (V1)");
        near(cog::look_mm(), 16.0, 0.0, "cog::look_mm default (V1)");
        assert!(!cog::fold_bound_absolute(), "no absolute bound unset");
        near(
            cog::fold_bound_mm(63.6),
            63.6,
            0.0,
            "relative fold bound passthrough",
        );
        near(
            cog::off_axis_mm(V1_REST),
            17.851,
            0.03,
            "V1 lamp-4ace rest off-axis",
        );
    }
    println!("ALL OK");
}
