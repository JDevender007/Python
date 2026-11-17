<div align="center">

# 👁️ Computer Vision Projects

### Five image pipelines built from first principles, then checked against OpenCV. The subject is not the demo picture — it is the definition: an edge is a kernel plus a border policy, a corner is a property of a neighbourhood, a threshold is a decision, "moved" depends on which model of the background you chose, and a detection is not a track.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-From%20Scratch-013243?style=for-the-badge&logo=numpy&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-Cross--checked-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)

</div>

---

# 📖 About

Every project here loads bundled images from `data/` (or generates them procedurally, then writes
them there once), runs a hand-written NumPy pipeline over the pixels, and uses **OpenCV as an
independent witness** rather than as the implementation. No model weights, no network, no GUI: images
are read and written with Pillow, the maths is `numpy`, and previews are printed as ASCII so the
output is reviewable in a terminal.

The interesting part is not the convolution. It is that **a pixel operation is a claim about what an
image is**, and each project is built around a different place where that claim quietly stops holding:

- an edge detector is a kernel plus an unstated border policy
- a "corner" is a threshold on a response you defined yourself
- a segmentation is only as good as the threshold you picked
- "this pixel moved" is meaningless until you say what the background is
- a blob in frame 12 is a detection; a path across 24 frames is a different object

**The lesson of each project is different, on purpose.** Five variations on "run a cv2 function"
would teach nothing; five distinct ways an image pipeline can be confidently wrong is the subject.

- **Edge_Detector** — *an edge is a definition, not a fact.* Sobel, Prewitt and the Laplacian are
  three kernels producing three different "edges" from the same pixels, and each one needs a border
  policy before it can be evaluated at all. The rebuild writes all three as 3×3 convolutions with
  `reflect-101` padding in pure NumPy, keeps `cv2` out of the maths and uses it only as a witness,
  and checks the gradient magnitude against the **analytic slope of a ramp image** (agreement to
  `1e-6`) — then reports an honest number for how much Sobel and Canny actually share
  (**IoU 0.447**), because they are not the same operator.
- **Feature_Detector** — *invariance is a claim you test, not a property you assume.* A Harris corner
  is `R = det(M) − k·tr(M)²` on a smoothed structure tensor, so `k`, the window size, the response
  threshold and the suppression radius all change which points exist. The rebuild builds the tensor
  and the integral-image box filter by hand, recovers **9/9 checkerboard corners**, proves the
  response is **brightness invariant**, and then tests the thing that actually matters downstream:
  ORB keypoints between a scene and its shifted copy recover the translation — **measured
  (17.0, 9.0) against a true (17, 9) shift**.
- **Image_Segmentation** — *a threshold is a decision with a cost on both sides.* Otsu picks a cut
  from between-class variance, so it is a statistic of the histogram, not a property of the objects;
  k-means is a partition, so the seed decides the answer; connected components are 4- or
  8-connectivity before they are anything else. The rebuild implements all three, matches OpenCV's
  Otsu value exactly, matches its component labelling on **7 regions**, and requires k-means to be
  **deterministic with monotonically non-increasing SSE** across iterations — with all four modes
  runnable from one CLI.
- **Motion_Analyzer** — *"which pixels moved?" has no answer until you name the background.* Frame
  differencing compares against the previous frame and therefore reports almost everything in a
  moving scene; a running-average background compares against a model and therefore ignores a static
  object, which is the correct answer. The rebuild builds both, runs them on a **20-frame** synthetic
  sequence with ground truth, requires the difference method to catch **every moving frame**, the
  background method to catch **every frame including the first**, the static object to be ignored,
  and a newly appearing object to be gated out by the warm-up — then adds hand-written dilate/erode
  so noise does not become "motion".
- **Object_Tracker** — *detection is not tracking.* A centroid per frame is a measurement; a path
  needs an association rule, and the honest one is a maximum jump: a blob further than `--max-jump`
  pixels from the previous position is a new object, not a continuation. The rebuild tracks two
  coloured balls across **24 frames** generated with known positions, requires a **tracking error of
  at most 1.5 px** against ground truth, verifies the recovered directions of travel, checks blob
  area, and returns `None` on an empty frame instead of inventing a position.

**Every claim is checkable.** Each demo prints `Cross-checks OK: ...` with the numbers it verified,
then `Demo completed successfully.`; run it twice and the bytes match, run it with `--quiet` and it
writes nothing at all.

The libraries used are `numpy`, `opencv-python` (as a cross-check only), and Pillow for image I/O.
Nothing reads a clock, opens a socket, or writes into the repository: rendered masks and JSON go only
where you point them (or into the gitignored `output/`).

---

# 🎓 Learning Objectives

- Implement 2-D convolution by hand and choose a border policy explicitly
- Recognise that Sobel, Prewitt and Laplacian are three definitions, not three qualities
- Validate a numeric gradient against an analytic one on a synthetic ramp
- Compare your operator to a library detector without replacing your operator with it
- Build the Harris structure tensor and explain what `k` and the window size do
- Test invariance claims (brightness, translation) instead of asserting them
- Recover a known image translation from descriptor matches and report the error
- Implement Otsu from between-class variance and match a reference implementation exactly
- Treat k-means as a seeded, iterative algorithm with a monotone objective
- Distinguish 4-connectivity from 8-connectivity in component labelling
- Contrast frame differencing with a running-average background model
- Use a warm-up period so a background model does not report the whole scene as motion
- Apply morphological opening/closing to remove speckle before measuring motion
- Separate detection (a centroid) from tracking (an association rule)
- Gate a detection by distance so a spurious blob cannot teleport a track
- Score tracking against ground truth in pixels rather than by eye

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Edge_Detector | Sobel/Prewitt/Laplacian from scratch, analytic-ramp validation, Canny IoU, ASCII maps. | 50 | ✅
02 | Feature_Detector | Harris corners from scratch, integral-image box filter, ORB matching, shift recovery. | 64 | ✅
03 | Image_Segmentation | Otsu, k-means and connected components from scratch, all cross-checked against OpenCV. | 61 | ✅
04 | Motion_Analyzer | Frame differencing vs running background, from-scratch morphology, motion statistics. | 62 | ✅
05 | Object_Tracker | Colour-blob centroids, max-jump association, 24-frame ground-truth error reporting. | 51 | ✅

**Total: 288 tests.**

---

# 🧠 Concepts Covered

- Grayscale conversion, `uint8` vs float pixel arithmetic, and clipping
- 3×3 convolution kernels and `reflect-101` border padding
- Gradient operators: Sobel, Prewitt, Laplacian; magnitude and direction
- Canny: non-maximum suppression and hysteresis thresholds
- Jaccard overlap as a way to compare two edge maps honestly
- The structure tensor, Harris response, and local-maximum suppression
- Integral images as an O(1) box filter and the `k` sensitivity of Harris
- ORB keypoints, binary descriptors, and Lowe's ratio test
- Recovering a rigid translation from matched keypoints
- Otsu's between-class variance and the threshold it implies
- k-means clustering on pixel colours: initialisation, seeding, and SSE monotonicity
- Connected-component labelling with 4- and 8-connectivity
- Frame differencing and its dependence on object motion magnitude
- Running-average background modelling, learning rate, and warm-up
- Binary morphology: dilation, erosion, opening, closing
- Centroid extraction from a boolean mask
- Nearest-previous-position association and a maximum-jump gate
- Ground-truth error metrics in pixels
- Procedural sample generation so the data is reproducible, not downloaded
- Determinism: fixed seeds, byte-identical demo re-runs

---

# 📁 Repository Structure

```text
18_Computer_Vision/
│
├── Edge_Detector/
│   ├── src/    edges.py, main.py
│   ├── tests/  test_edges.py
│   └── data/   gradient_ramp.png, shapes.png, noisy_step.png
│
├── Feature_Detector/
│   ├── src/    features.py, main.py
│   ├── tests/  test_features.py
│   └── data/   checkerboard.png, scene_a.png, scene_b.png
│
├── Image_Segmentation/
│   ├── src/    segmentation.py, main.py
│   ├── tests/  test_segmentation.py
│   └── data/   otsu_shapes.png, color_blocks.png, components.png
│
├── Motion_Analyzer/
│   ├── src/    motion.py, main.py
│   ├── tests/  test_motion.py
│   └── data/   truth.csv
│
└── Object_Tracker/
    ├── src/    tracker.py, main.py
    ├── tests/  test_tracker.py
    └── data/   truth.csv
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI, a
`tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a `.gitignore`, and a
`README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 18_Computer_Vision/Edge_Detector

python src/main.py --demo                                  # offline, deterministic, exit 0
python src/main.py --demo --quiet                           # prints nothing at all
python src/main.py --file data/shapes.png --method canny --json out.json
python src/main.py --file data/noisy_step.png --method sobel --low 40 --high 90
python -m pytest tests -q                                   # the suite
```

Every project supports `--demo` (plus `--quiet`) and `--json <path>`, and adds its own flags
(`--file`, `--frames`, `--method`, `--mode`, `--threshold`, `--low`/`--high`, `--clusters`,
`--connectivity`, `--seed`, `--colour`, `--max-jump`). Nothing opens a connection, and no demo writes
into the repository: PNGs and JSON go only where you point them.

---

# ✅ Verify the whole category

```powershell
Get-ChildItem -Directory | ForEach-Object {
    Push-Location $_
    python -m compileall -q src tests
    python -m pytest tests -q
    python src\main.py --demo
    python src\main.py --demo --quiet
    Pop-Location
}
```

The gates each project must pass, and does:

1. `compileall` on `src` and `tests` exits 0
2. `pytest` passes with no skips, 50+ tests
3. `--demo` exits 0 and ends with `Cross-checks OK: ...` then `Demo completed successfully.`
4. `--demo` twice produces byte-identical output, and `--demo --quiet` prints nothing at all
5. no non-ASCII byte in `src/`, `tests/` (binary sample images are exempt)

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why an edge map is a definition, and why two edge detectors disagree on the same image
- Why a border policy is part of the algorithm rather than an implementation detail
- Why an analytic test image is stronger evidence than a pretty result
- Why using a library as a witness is different from using it as the implementation
- Why a corner response needs a threshold, and a threshold needs a reason
- Why invariance must be a test, not a bullet point
- Why a segmentation with an unexplained threshold is a guess with a picture attached
- Why k-means without a fixed seed is not reproducible, and SSE is the check
- Why "the pixel moved" depends entirely on the background model
- Why a warm-up period is what stops a tracker reporting the entire scene
- Why detection and tracking are separate problems with separate failure modes
- Why a tracking error in pixels beats a screenshot of a box that "looks right"
- How to make an image pipeline reproducible byte for byte

---

# 🧩 Patterns Included

Parsing — `load_image`, `load_color_image`, `load_frames`, `load_truth`, `parse_map`
Validation — `EdgeError`, `FeatureError`, `SegError`, `MotionError`, `TrackerError`
Convolution — `convolve2d`, `box_filter`, `harris_response`, `harris_corners`
Gradients — `sobel`, `prewitt`, `laplacian`, `magnitude`, `threshold_mask`, `canny_edges`
Features — `orb_keypoints`, `match_descriptors`, `displacement_stats`, `corner_mask`
Segmentation — `otsu_threshold`, `otsu_mask`, `kmeans_segment`, `connected_components`
Motion — `frame_difference`, `running_background`, `background_mask`, `dilate`, `erode`, `clean_mask`
Tracking — `colour_mask`, `blob_centroid`, `detect`, `track_colour`, `position_errors`, `path_stats`
Rendering — `ascii_map`, `ascii_overlay`, `trajectory_map`, `render_report`, `to_dict`
Samples — `generate_samples`, `bundle_samples`, `generate_sequence`, `bundle_frames`
Testing — analytic-ramp checks, OpenCV cross-checks, invariance tests, ground-truth errors,
CLI paths, quiet-mode silence

---

# 🚀 Future Improvements

- A shared convolution kernel so all five projects use one border-policy implementation
- Sub-pixel corner refinement and a proper reprojection test instead of a single shift
- A Watershed segmentation beside Otsu and k-means for touching objects
- Optical flow as a third motion model, compared against differencing on the same sequence
- A constant-velocity Kalman tracker beside the max-jump association rule
- Multi-colour tracking with occlusion handling and identity re-assignment
- A category-wide `audit` harness that prints all five evidence tables in one shape

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with a clear message.
4. Push the branch.
5. Open a Pull Request.

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
