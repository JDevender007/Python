<div align="center">

# 👁️ Computer Vision Projects

### Five offline computer-vision projects: edge detection, image segmentation, feature detection and matching, colour-blob tracking, and motion analysis — all with bundled procedural imagery.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

This category covers the classical computer-vision pipeline from pixels to motion: gradients and edges, region segmentation, distinctive features and matching, object tracking across frames, and temporal motion detection. The interesting algorithms are implemented **from first principles** — Sobel/Prewitt/Laplacian kernels, Otsu's criterion, k-means++, BFS connected components, the Harris structure tensor, centroids, frame differencing and morphology — while OpenCV is used to decode images and to *cross-check* results.

Every project runs **fully offline** with `--demo`. Synthetic images and frame sequences are generated deterministically and bundled as PNGs/CSVs in `data/`; the demos verify those files against their generator before asserting anything, so a corrupted asset fails loudly rather than silently changing the numbers. No network, no API keys, no dataset downloads.

---

# 🎯 Learning Objectives

- Implement convolution kernels and edge operators, then prove them against analytic slopes and cv2
- Apply Otsu's between-class variance criterion and validate it against `cv2.THRESH_OTSU`
- Cluster pixels with k-means++ and evaluate with inertia
- Label connected regions with explicit BFS and 4/8-connectivity
- Compute the Harris response and suppress plateaus correctly
- Match ORB descriptors with a ratio test and recover a known translation
- Track coloured objects with centroid association and gate on jump distance
- Separate moving objects from static ones with background subtraction
- Keep demos deterministic, self-verifying and fast
- Bundle procedurally generated data instead of downloading datasets

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Edge_Detector | Sobel/Prewitt/Laplacian from scratch + cv2 Canny cross-check. | ✅
02 | Image_Segmentation | Otsu + k-means + BFS connected components, cv2-verified. | ✅
03 | Feature_Detector | Harris corners from scratch + ORB matching recovering a (17, 9) shift. | ✅
04 | Object_Tracker | Colour-blob centroids over 24 frames, ≤1.5 px vs ground truth. | ✅
05 | Motion_Analyzer | Frame differencing + causal background model + morphology. | ✅

---

# 💡 Concepts Covered

- Discrete convolution and separable kernels
- Sobel / Prewitt / Laplacian operators and border handling
- Gradient magnitude, hysteresis, and Canny comparison
- Otsu thresholding via cumulative histogram statistics
- k-means++ seeding, vectorised assignment, inertia
- Connected components with BFS and connectivity choice
- Structure tensor, Harris response, non-maximum suppression
- FAST keypoints, BRIEF descriptors, Hamming matching, Lowe's ratio test
- Colour thresholding, centroid estimation, nearest-neighbour association
- Frame differencing vs background subtraction and ghost artifacts
- Morphological opening/closing with a square element
- Deterministic procedural data generation for reproducible CV tests

---

# 📁 Repository Structure

```text
18_Computer_Vision/
│
├── Edge_Detector/
├── Image_Segmentation/
├── Feature_Detector/
├── Object_Tracker/
├── Motion_Analyzer/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library modules
├── tests/            # pytest test suite
├── data/             # bundled deterministic imagery / frames / CSV
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- NumPy (kernels, histograms, k-means, structure tensors, morphology)
- OpenCV (image decoding, Canny/ORB cross-checks, procedural drawing)
- argparse / json / csv / logging
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Edge Detector | ✅ |
| Image Segmentation | ✅ |
| Feature Detector | ✅ |
| Object Tracker | ✅ |
| Motion Analyzer | ✅ |

**Completed:** **5 / 5 Projects**

---

# ▶️ Quick Start

```bash
cd 18_Computer_Vision/Edge_Detector

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

---

# 📚 Skills Developed

- Translating mathematical definitions into vectorised NumPy
- Validating hand-written algorithms against a reference library
- Designing synthetic data whose ground truth is known exactly
- Evaluating detectors with IoU, pixel error and coverage metrics
- Understanding when simple methods fail (plateaus, edge clipping, ghosts)
- Building deterministic, self-checking demos
- Automated Testing with pytest

---

# 🚀 Key Learning Outcomes

- Detect edges and prove the kernels analytically
- Segment images three different ways and cross-check each
- Find and match keypoints across views, recovering the transform
- Track objects and quantify error against ground truth
- Distinguish motion from static structure with a causal background model

---

# 🔮 Future Enhancements

- Canny hysteresis implemented from scratch (not just cross-checked)
- SIFT/SURF comparison alongside ORB
- Homography estimation with RANSAC from the recovered matches
- Kalman-filtered tracking trajectories
- Optical flow (Lucas–Kanade) as a third motion detector

---

# 🤝 Contributions

Suggestions, improvements, and feedback are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
