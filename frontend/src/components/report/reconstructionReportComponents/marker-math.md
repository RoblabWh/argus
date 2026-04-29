# Marker Position Math — ReconstructionViewerTab

This document explains how the spherical yaw/pitch angles for each keyframe
marker are derived from the `keyframe_trajectory.txt` produced by Stella-VSLAM.

---

## 1. Input: TUM trajectory format

Stella-VSLAM saves keyframe poses as `keyframe_trajectory.txt` in TUM format:

```
timestamp  tx  ty  tz  qx  qy  qz  qw
```

**`(tx, ty, tz)`** — camera position in the **world frame** (T_wc convention).
This is a direct 3D coordinate: the origin of the camera's local frame expressed
in world coordinates. Example: tz grows monotonically as the UAV flies forward.

**`(qx, qy, qz, qw)`** — unit quaternion **q_wc** representing the rotation that
takes a vector from the *camera* frame to the *world* frame.
More precisely: `p_world = R(q_wc) · p_camera + t_wc`.

> **Convention note.** Stella-VSLAM tracks poses as T_cw internally but saves the
> trajectory as T_wc (inverted) so that `(tx, ty, tz)` is the intuitive camera
> position. This is the standard TUM benchmark ground-truth format.

---

## 2. Goal

For a currently-displayed keyframe **C** and every other keyframe **T**, we want
the spherical coordinates **(yaw, pitch)** — in the viewer's frame of reference —
that point from C toward T. These are fed directly to Photo Sphere Viewer as
marker positions.

---

## 3. Step-by-step derivation

### Step 1 — World-space displacement vector

```
Δp_world = (T.tx − C.tx,  T.ty − C.ty,  T.tz − C.tz)
```

Both translations are already camera positions in the world frame, so the
difference is the vector from C to T expressed in world coordinates.

Normalize to a unit direction:

```
d = Δp_world / |Δp_world|      (d is a unit vector in world space)
```

### Step 2 — Transform into current camera space

We need **d** expressed in the local coordinate frame of camera C (because PSV
angles are relative to what the camera is looking at, not world north/east).

The stored quaternion q_wc rotates *camera → world*.
To go the other way (*world → camera*), we use the **conjugate**:

```
q_cw = conjugate(q_wc) = (−qx, −qy, −qz, qw)
```

Applying it via the quaternion sandwich product `q v q*`:

```
d_cam = q_cw ⊗ d ⊗ q_cw*
      = R_cw · d
```

In code (`quatRotate`), this is:

```typescript
const cam = quatRotate(
  -current.qx, -current.qy, -current.qz, current.qw,   // q_cw
  dx / dist,    dy / dist,    dz / dist                  // d
);
```

The efficient expanded form of the sandwich product used in `quatRotate` is:

```
t  = 2 · (q_vec × v)
v' = v + qw·t + (q_vec × t)
```

where `q_vec = (qx, qy, qz)` is the vector part of the quaternion.

### Step 3 — Camera coordinate system (OpenCV convention)

After step 2, `d_cam = (x, y, z)` is in the OpenCV camera frame:

| axis | direction |
|------|-----------|
| +Z   | forward (into the scene) |
| +X   | right |
| +Y   | **down** |

### Step 4 — Convert to spherical angles

**Yaw** (azimuth, horizontal angle):
```
yaw = atan2(x, z)     [radians]
```
- yaw = 0   → straight ahead (+Z)
- yaw = π/2 → right (+X)
- yaw = −π/2 → left (−X)

**Pitch** (elevation, vertical angle):
```
pitch = −atan2(y, sqrt(x² + z²))     [radians]
```
The negation converts from OpenCV's +Y-down to PSV's +pitch-up convention:
- pitch = 0   → horizontal
- pitch > 0   → above horizon  (target is above current camera position)
- pitch < 0   → below horizon

These two values are passed directly to the PSV `MarkersPlugin` as
`{ yaw, pitch }` in radians.

---

## 4. Why the conjugate matters

If the quaternion is used **without conjugating**, the rotation is applied in the
wrong direction (camera→world instead of world→camera). For early/straight-flight
frames where `q_wc ≈ identity`, the error is negligible. But once the UAV rotates
significantly (e.g. a heading change of ≥ 30°), the entire marker cluster rotates
to the wrong position on the sphere while keeping its internal shape intact —
exactly the symptom that motivated this fix.

Analogously, the working reference implementation (old Pannellum viewer) stored
raw 4×4 T_cw matrices, inverted them to T_wc, extracted R_wc, and explicitly
**transposed** it to get R_cw before applying it to the delta. Transposing a
rotation matrix is identical to conjugating the corresponding quaternion.

---

## 5. Full formula in one place

```
Given:
  C = current keyframe  { tx_C, ty_C, tz_C, qx_C, qy_C, qz_C, qw_C }
  T = target  keyframe  { tx_T, ty_T, tz_T }

Δ = (tx_T − tx_C,  ty_T − ty_C,  tz_T − tz_C)
d = Δ / |Δ|

q_cw = (−qx_C, −qy_C, −qz_C, qw_C)

d_cam = R(q_cw) · d   (quaternion sandwich product)

yaw   = atan2(d_cam.x, d_cam.z)
pitch = −atan2(d_cam.y, sqrt(d_cam.x² + d_cam.z²))
```

---

## 6. Marker appearance extras

Beyond placement, `computeMarkersForIndex` also computes:

- **Size** — scales quadratically with distance so nearby frames appear as
  larger dots and distant frames shrink (`scale()` function).
- **Color** — interpolates from cyan to violet based on the target frame's
  timestamp, giving a visual sense of temporal ordering across the whole
  trajectory cloud.
