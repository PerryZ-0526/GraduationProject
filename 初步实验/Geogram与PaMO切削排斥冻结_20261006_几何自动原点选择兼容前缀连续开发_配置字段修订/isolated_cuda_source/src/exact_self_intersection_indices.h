#pragma once
#include <vector>

// 对实际FP32坐标逐值转double后作精确判定，返回原始面编号。
std::vector<unsigned int> exact_self_intersection_indices(
    const float* vertices, const int* faces, int n_vertices, int n_faces,
    bool& topology_valid);
