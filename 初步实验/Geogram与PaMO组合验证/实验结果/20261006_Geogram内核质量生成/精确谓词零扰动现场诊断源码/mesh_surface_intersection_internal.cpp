/*
 *  COPYRIGHT (c) 2000-2022 Inria
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions are met:
 *
 *  * Redistributions of source code must retain the above copyright notice,
 *  this list of conditions and the following disclaimer.
 *  * Redistributions in binary form must reproduce the above copyright notice,
 *  this list of conditions and the following disclaimer in the documentation
 *  and/or other materials provided with the distribution.
 *  * Neither the name of the ALICE Project-Team nor the names of its
 *  contributors may be used to endorse or promote products derived from this
 *  software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 *  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 *  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 *  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 *  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 *  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 *  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 *  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 *  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 *  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 *  POSSIBILITY OF SUCH DAMAGE.
 *
 *  Contact: Bruno Levy
 *
 *     https://www.inria.fr/fr/bruno-levy
 *
 *     Inria,
 *     Domaine de Voluceau,
 *     78150 Le Chesnay - Rocquencourt
 *     FRANCE
 *
 */

#include <geogram/mesh/mesh_surface_intersection_internal.h>
#include <geogram/delaunay/delaunay_triangle.h>
#include <mutex>
#include <set>
#include <cmath>
#include <limits>
#include <cstdio>
// 诊断文件逐次独立编号，不改变区域生成和所有接受判据。
#include <atomic>
#include <fstream>
#include <iomanip>
#include <geogram/mesh/mesh_surface_intersection.h>
#include <geogram/basic/debug_stream.h>
#include <geogram/basic/boolean_expression.h>
#include <stack>

namespace {
    using namespace GEO;

    /**
     * \brief Computes the exact intersection between the support
     *  planes of three triangles
     * \param[in] p1 , p2 , p3 the three vertices of the first triangle
     * \param[in] q1 , q2 , q3 the three vertices of the second triangle
     * \param[in] r1 , r2 , r3 the three vertices of the third triangle
     * \param[out] result the exact intersection between the three planes
     *  if it exsists
     * \retval true if the planes have an intersection
     * \retval false otherwise
     */
    bool get_three_planes_intersection(
        MeshSurfaceIntersection::ExactPoint& result,
        const vec3& p1, const vec3& p2, const vec3& p3,
        const vec3& q1, const vec3& q2, const vec3& q3,
        const vec3& r1, const vec3& r2, const vec3& r3
    ) {
        exact::vec3 N1 = triangle_normal<exact::vec3>(p1,p2,p3);
        exact::vec3 N2 = triangle_normal<exact::vec3>(q1,q2,q3);
        exact::vec3 N3 = triangle_normal<exact::vec3>(r1,r2,r3);

        exact::vec3 B(
            dot(N1,exact::vec3(p1)),
            dot(N2,exact::vec3(q1)),
            dot(N3,exact::vec3(r1))
        );

        result.w = det3x3(
            N1.x, N1.y, N1.z,
            N2.x, N2.y, N2.z,
            N3.x, N3.y, N3.z
        );

        if(result.w.sign() == ZERO) {
            return false;
        }

        result.x = det3x3(
            B.x, N1.y, N1.z,
            B.y, N2.y, N2.z,
            B.z, N3.y, N3.z
        );

        result.y = det3x3(
            N1.x, B.x, N1.z,
            N2.x, B.y, N2.z,
            N3.x, B.z, N3.z
        );

        result.z = det3x3(
            N1.x, N1.y, B.x,
            N2.x, N2.y, B.y,
            N3.x, N3.y, B.z
        );

        return true;
    }

    /**
     * \brief Computes the exact intersection between the support plane
     *  of a triangle and the support line of a segment
     * \pre The intersection exists
     * \param[in] p1 , p2 , p3 the three vertices of the triangle
     * \param[in] q1 , q2 the two vertices of the segment
     * \return the exact intersection between the plane and the line
     */
    MeshSurfaceIntersection::ExactPoint plane_line_intersection(
        const vec3& p1, const vec3& p2, const vec3& p3,
        const vec3& q1, const vec3& q2
    ) {
        // Moller & Trumbore's algorithm
        // see: https://stackoverflow.com/questions/42740765/
        //  intersection-between-line-and-triangle-in-3d
        exact::vec3 D   = make_vec3<exact::vec3>(q1,q2);
        exact::vec3 E1  = make_vec3<exact::vec3>(p1,p2);
        exact::vec3 E2  = make_vec3<exact::vec3>(p1,p3);
        exact::vec3 AO  = make_vec3<exact::vec3>(p1,q1);
        exact::vec3 N   = cross(E1,E2);
        exact::scalar d  = -dot(D,N);
        geo_debug_assert(d.sign() != ZERO);
        exact::rational t(dot(AO,N),d);
        return mix(t,q1,q2);
    }
}

namespace GEO {

    void MeshInTriangle::Vertex::print(std::ostream& out) const {
        if(sym.f1 != NO_INDEX) {
            out << " ( ";
            out << sym.f1;
            out << region_to_string(sym.R1).substr(2);
        }
        if(sym.f2 != NO_INDEX) {
            out << " /\\ ";
            out << sym.f2;
            out << region_to_string(sym.R2).substr(2);
        }
        if(sym.f1 != NO_INDEX) {
            out << " ) ";
        }
    }

    MeshInTriangle::ExactPoint MeshInTriangle::Vertex::compute_geometry() {
        // Case 1: f1 vertex
        if(region_dim(sym.R1) == 0) {
            index_t lv = index_t(sym.R1) - index_t(T1_RGN_P0);
            geo_debug_assert(lv < 3);
            mesh_vertex_index = mesh().facets.vertex(sym.f1,lv);
            vec3 p = mit->mesh_vertex(mesh_vertex_index);
            return ExactPoint(p);
        }

        geo_debug_assert(sym.f1 != NO_INDEX && sym.f2 != NO_INDEX);

        // Case 2: f2 vertex
        if(region_dim(sym.R2) == 0) {
            index_t lv = index_t(sym.R2) - index_t(T2_RGN_P0);
            geo_debug_assert(lv < 3);
            mesh_vertex_index = mesh().facets.vertex(sym.f2, lv);
            vec3 p = mit->mesh_vertex(mesh_vertex_index);
            return ExactPoint(p);
        }

        // case 3: f1 /\ f2 edge in 3D or f1 edge /\ f2 edge in 3D
        if(
            (region_dim(sym.R1) == 2 || region_dim(sym.R1) == 1) &&
            region_dim(sym.R2) == 1
        ) {
            vec3 p1 = mit->mesh_facet_vertex(sym.f1, 0);
            vec3 p2 = mit->mesh_facet_vertex(sym.f1, 1);
            vec3 p3 = mit->mesh_facet_vertex(sym.f1, 2);
            index_t e = index_t(sym.R2)-index_t(T2_RGN_E0);
            geo_debug_assert(e<3);
            vec3 q1 = mit->mesh_facet_vertex(sym.f2, (e+1)%3);
            vec3 q2 = mit->mesh_facet_vertex(sym.f2, (e+2)%3);

            bool seg_seg_two_D = (
                region_dim(sym.R1) == 1 &&
                PCK::orient_3d(p1,p2,p3,q1) == ZERO &&
                PCK::orient_3d(p1,p2,p3,q2) == ZERO) ;

            if(!seg_seg_two_D) {
                return plane_line_intersection(p1,p2,p3,q1,q2);
            }
        }

        // case 4: f1 edge /\ f2
        if(region_dim(sym.R1) == 1 && region_dim(sym.R2) == 2) {
            index_t e = index_t(sym.R1)-index_t(T1_RGN_E0);
            geo_debug_assert(e<3);
            vec3 p1 = mit->mesh_facet_vertex(sym.f2,0);
            vec3 p2 = mit->mesh_facet_vertex(sym.f2,1);
            vec3 p3 = mit->mesh_facet_vertex(sym.f2,2);
            vec3 q1 = mit->mesh_facet_vertex(sym.f1, (e+1)%3);
            vec3 q2 = mit->mesh_facet_vertex(sym.f1, (e+2)%3);
            return plane_line_intersection(p1,p2,p3,q1,q2);
        }

        // case 5: f1 edge /\ f2 edge in 2D
        if(region_dim(sym.R1) == 1 && region_dim(sym.R2) == 1) {
            index_t e1 = index_t(sym.R1) - index_t(T1_RGN_E0);
            geo_debug_assert(e1 < 3);
            index_t e2 = index_t(sym.R2) - index_t(T2_RGN_E0);
            geo_debug_assert(e2 < 3);
            vec2 p1 = mit->mesh_facet_vertex_UV(sym.f1, (e1+1)%3);
            vec2 p2 = mit->mesh_facet_vertex_UV(sym.f1, (e1+2)%3);
            vec2 q1 = mit->mesh_facet_vertex_UV(sym.f2, (e2+1)%3);
            vec2 q2 = mit->mesh_facet_vertex_UV(sym.f2, (e2+2)%3);
            vec3 P1 = mit->mesh_facet_vertex(sym.f1, (e1+1)%3);
            vec3 P2 = mit->mesh_facet_vertex(sym.f1, (e1+2)%3);

            exact::vec2 D1 = make_vec2<exact::vec2>(p1,p2);
            exact::vec2 D2 = make_vec2<exact::vec2>(q1,q2);
            exact::scalar d = det(D1,D2);
            geo_debug_assert(d.sign() != ZERO);
            exact::vec2 AO = make_vec2<exact::vec2>(p1,q1);
            exact::rational t(det(AO,D2),d);
            return mix(t,P1,P2);
        }

        // Normally we enumerated all possible cases
        geo_assert_not_reached;
    }

    void MeshInTriangle::Vertex::init_geometry(const ExactPoint& P) {
        point_exact = P;
        Numeric::optimize_number_representation(point_exact);
#ifndef GEOGRAM_USE_EXACT_NT
        l = (geo_sqr(P[mit->u_]) + geo_sqr(P[mit->v_])).estimate() /
            geo_sqr(P.w).estimate() ;
#endif
    }

    MeshInTriangle::MeshInTriangle(MeshSurfaceIntersection& EM) :
        exact_mesh_(EM),
        mesh_(EM.readonly_mesh()),
        f1_(NO_INDEX),
        dry_run_(false),
        use_pred_cache_insert_buffer_(false)
    {
#ifdef GEOGRAM_USE_EXACT_NT
        CDTBase2d::exact_incircle_ = true;
#else
        // Since incircle() with expansions computes approximated
        // lifted coordinate, we need to activate additional
        // checks for Delaunayization.
        CDTBase2d::exact_incircle_ = false;
#endif
    }

    void MeshInTriangle::clear() {
        vertex_.resize(0);
        edges_.resize(0);
        f1_ = NO_INDEX;
        pred_cache_.clear();
        pred_cache_insert_buffer_.resize(0);
        use_pred_cache_insert_buffer_ = false;
        CDTBase2d::clear();
    }

    void MeshInTriangle::begin_facet(index_t f) {
        f1_ = f;

        latest_f2_ = NO_INDEX;
        latest_f2_count_ = 0;

        vec3 p1 = mesh_facet_vertex(f,0);
        vec3 p2 = mesh_facet_vertex(f,1);
        vec3 p3 = mesh_facet_vertex(f,2);

        geo_debug_assert(!PCK::aligned_3d(p1,p2,p3));

        f1_normal_axis_ = PCK::triangle_normal_axis(
            p1,p2,p3
        );

        u_ = coord_index_t((f1_normal_axis_ + 1) % 3);
        v_ = coord_index_t((f1_normal_axis_ + 2) % 3);
        for(index_t lv=0; lv<3; ++lv) {
            vertex_.push_back(Vertex(this, f, lv));
        }

        CDTBase2d::create_enclosing_triangle(0,1,2);

        edges_.push_back(Edge(1,2));
        edges_.push_back(Edge(2,0));
        edges_.push_back(Edge(0,1));

        has_planar_isect_ = false;
    }

    index_t MeshInTriangle::add_vertex(
        index_t f2, TriangleRegion R1, TriangleRegion R2
    ) {
        geo_debug_assert(f1_ != NO_INDEX);

        // If the same f2 comes more than twice, then
        // we got a planar facet /\ facet intersection
        // (and it is good to know it, see get_constraints())
        if(f2 != NO_INDEX && f2 == latest_f2_) {
            ++latest_f2_count_;
            if(latest_f2_count_ > 2) {
                has_planar_isect_ = true;
            }
        } else {
            latest_f2_ = f2;
            latest_f2_count_ = 0;
        }

        // If vertex is a macro-vertex, return it directly.
        if(region_dim(R1) == 0) {
            return index_t(R1);
        }

        // Create the vertex
        vertex_.push_back(Vertex(this, f1_, f2, R1, R2));

        // Insert it into the triangulation
        index_t v = CDTBase2d::insert(vertex_.size()-1);

        // If it was an existing vertex, return the existing vertex
        if(vertex_.size() > CDTBase2d::nv()) {
            vertex_.pop_back();
        }
        return v;
    }

    void MeshInTriangle::add_edge(
        index_t f2,
        TriangleRegion AR1, TriangleRegion AR2,
        TriangleRegion BR1, TriangleRegion BR2
    ) {
        index_t v1 = add_vertex(f2, AR1, AR2);
        index_t v2 = add_vertex(f2, BR1, BR2);

        // If both extremities are on the same edge of f1,
        // we do not add the edge, because it will be generated
        // when remeshing the edge of f1
        if(region_dim(regions_convex_hull(AR1,BR1)) == 1) {
            return;
        }

        // Generate also the combinatorial information of the edge,
        // that indicates whether both extremities are on the same
        // edge of f2 (useful later to compute the intersections)
        edges_.push_back(Edge(v1,v2,f2,regions_convex_hull(AR2,BR2)));

        // Constraints will be added to the triangulation during commit()
    }

    void MeshInTriangle::commit() {

        for(const Edge& E: edges_) {
            CDTBase2d::insert_constraint(E.v1, E.v2);
        }

        if(dry_run_) {
            return;
        }

        // Protect global mesh from concurrent accesses
        exact_mesh_.lock();

        // Create vertices and facets in target mesh
        for(index_t i=0; i<vertex_.size(); ++i) {
            // Vertex already exists in this MeshInTriangle
            if(vertex_[i].mesh_vertex_index != NO_INDEX) {
                continue;
            }
            vertex_[i].mesh_vertex_index =
                exact_mesh_.find_or_create_exact_vertex(
                    vertex_[i].point_exact
                );
        }

        // Create facets in target mesh
        for(index_t t=0; t<CDTBase2d::nT(); ++t) {
            index_t i = CDTBase2d::Tv(t,0);
            index_t j = CDTBase2d::Tv(t,1);
            index_t k = CDTBase2d::Tv(t,2);
            i = vertex_[i].mesh_vertex_index;
            j = vertex_[j].mesh_vertex_index;
            k = vertex_[k].mesh_vertex_index;
            index_t new_t = target_mesh().facets.create_triangle(i,j,k);
            // Copy all attributes from initial facet
            target_mesh().facets.attributes().copy_item(new_t, f1_);
        }

        // We are done with modification in the mesh
        exact_mesh_.unlock();
    }

    void MeshInTriangle::get_constraints(Mesh& M, bool with_edges) const {
        if(M.vertices.nb() == 0) {
            M.vertices.set_dimension(2);
            for(index_t v=0; v<vertex_.size(); ++v) {
                vec2 p = vertex_[v].get_UV_approx();
                M.vertices.create_vertex(p.data());
            }
        }
        if(with_edges && M.edges.nb() == 0) {
            for(const Edge& E: edges_) {
                M.edges.create_edge(E.v1, E.v2);
            }
        }
    }

    /**
     * \brief Tests the parity of the permutation of a list of
     *  three distinct indices with respect to the canonical order.
     */
    static bool odd_order(index_t i, index_t j, index_t k) {
        // Implementation: sort the elements (bubble sort is OK for
        // such a small number), and invert parity each time
        // two elements are swapped.
        index_t tab[3] = { i, j, k};
        const int N = 3;
        bool result = false;
        for (int I = 0; I < N - 1; ++I) {
            for (int J = 0; J < N - I - 1; ++J) {
                if (tab[J] > tab[J + 1]) {
                    std::swap(tab[J], tab[J + 1]);
                    result = !result;
                }
            }
        }
        return result;
    }

    void MeshInTriangle::begin_insert_transaction() {
        use_pred_cache_insert_buffer_ = true;
    }

    void MeshInTriangle::commit_insert_transaction() {
        for(const auto& it: pred_cache_insert_buffer_) {
            pred_cache_[it.first] = it.second;
        }
        pred_cache_insert_buffer_.resize(0);
        use_pred_cache_insert_buffer_ = false;
    }

    void MeshInTriangle::rollback_insert_transaction() {
        pred_cache_insert_buffer_.resize(0);
        use_pred_cache_insert_buffer_ = false;
    }

    Sign MeshInTriangle::orient2d(index_t vx1,index_t vx2,index_t vx3) const {

        trindex K(vx1, vx2, vx3);

        if(use_pred_cache_insert_buffer_) {
            Sign result = PCK::orient_2d_projected(
                vertex_[K.indices[0]].point_exact,
                vertex_[K.indices[1]].point_exact,
                vertex_[K.indices[2]].point_exact,
                f1_normal_axis_
            );
            pred_cache_insert_buffer_.push_back(std::make_pair(K, result));
            if(odd_order(vx1,vx2,vx3)) {
                result = Sign(-result);
            }
            return result;
        }

        bool inserted;
        std::map<trindex, Sign>::iterator it;
        std::tie(it,inserted) = pred_cache_.insert(std::make_pair(K,ZERO));
        Sign result;

        if(inserted) {
            result = PCK::orient_2d_projected(
                vertex_[K.indices[0]].point_exact,
                vertex_[K.indices[1]].point_exact,
                vertex_[K.indices[2]].point_exact,
                f1_normal_axis_
            );
            it->second = result;
        } else {
            result = it->second;
        }

        if(odd_order(vx1,vx2,vx3)) {
            result = Sign(-result);
        }

        return result;
    }

    Sign MeshInTriangle::incircle(
        index_t v1,index_t v2,index_t v3,index_t v4
    ) const {
        exact::vec2h p1(
            vertex_[v1].point_exact[u_],
            vertex_[v1].point_exact[v_],
            vertex_[v1].point_exact.w
        );
        exact::vec2h p2(
            vertex_[v2].point_exact[u_],
            vertex_[v2].point_exact[v_],
            vertex_[v2].point_exact.w
        );
        exact::vec2h p3(
            vertex_[v3].point_exact[u_],
            vertex_[v3].point_exact[v_],
            vertex_[v3].point_exact.w
        );
        exact::vec2h p4(
            vertex_[v4].point_exact[u_],
            vertex_[v4].point_exact[v_],
            vertex_[v4].point_exact.w
        );
#ifdef GEOGRAM_USE_EXACT_NT
        return PCK::incircle_2d_SOS(p1,p2,p3,p4);
#else
        return PCK::incircle_2d_SOS_with_lengths(
            p1,p2,p3,p4,
            vertex_[v1].l,
            vertex_[v2].l,
            vertex_[v3].l,
            vertex_[v4].l
        );
#endif
    }

    index_t MeshInTriangle::create_intersection(
        index_t e1, index_t i, index_t j,
        index_t e2, index_t k, index_t l
    ) {
        geo_argused(i);
        geo_argused(j);
        geo_argused(k);
        geo_argused(l);

        ExactPoint I;
        get_edge_edge_intersection(e1,e2,I);
        vertex_.push_back(Vertex(this,I));
        index_t x = vertex_.size()-1;
        CDTBase2d::v2T_.push_back(NO_INDEX);
        geo_debug_assert(x == CDTBase2d::nv_);
        ++CDTBase2d::nv_;
        return x;
    }

    void MeshInTriangle::get_edge_edge_intersection(
        index_t e1, index_t e2, ExactPoint& I
    ) const {
        index_t f1 = f1_;
        index_t f2 = edges_[e1].sym.f2;
        index_t f3 = edges_[e2].sym.f2;

        geo_debug_assert(f1 != NO_INDEX);
        geo_debug_assert(f2 != NO_INDEX);
        geo_debug_assert(f3 != NO_INDEX);

        vec3 P[9] = {
            mesh_facet_vertex(f1,0), mesh_facet_vertex(f1,1),
            mesh_facet_vertex(f1,2),
            mesh_facet_vertex(f2,0), mesh_facet_vertex(f2,1),
            mesh_facet_vertex(f2,2),
            mesh_facet_vertex(f3,0), mesh_facet_vertex(f3,1),
            mesh_facet_vertex(f3,2)
        };

        if(!get_three_planes_intersection(
               I,
               P[0], P[1], P[2],
               P[3], P[4], P[5],
               P[6], P[7], P[8]
           )) {
            get_edge_edge_intersection_2D(e1,e2,I);
            return;
        }
    }

    void MeshInTriangle::get_edge_edge_intersection_2D(
        index_t e1, index_t e2, ExactPoint& I
    ) const {
        const Edge& E1 = edges_[e1];
        const Edge& E2 = edges_[e2];

        if(
            region_dim(E1.sym.R2) == 1 &&
            region_dim(E2.sym.R2) == 1
        ) {
            index_t le1 = index_t(E1.sym.R2)-index_t(T2_RGN_E0);
            index_t le2 = index_t(E2.sym.R2)-index_t(T2_RGN_E0);
            geo_debug_assert(le1 < 3);
            geo_debug_assert(le2 < 3);

            vec2 p1_uv = mesh_facet_vertex_UV(E1.sym.f2, (le1+1)%3);
            vec2 p2_uv = mesh_facet_vertex_UV(E1.sym.f2, (le1+2)%3);
            vec2 q1_uv = mesh_facet_vertex_UV(E2.sym.f2, (le2+1)%3);
            vec2 q2_uv = mesh_facet_vertex_UV(E2.sym.f2, (le2+2)%3);

            exact::vec2 C1 = make_vec2<exact::vec2>(p1_uv, p2_uv);
            exact::vec2 C2 = make_vec2<exact::vec2>(q2_uv, q1_uv);
            exact::vec2 B  = make_vec2<exact::vec2>(p1_uv, q1_uv);
            exact::scalar d = det(C1,C2);
            geo_debug_assert(d.sign() != ZERO);
            exact::rational t(det(B,C2),d);
            I = mix(
                t,
                mesh_facet_vertex(E1.sym.f2,(le1+1)%3),
                mesh_facet_vertex(E1.sym.f2,(le1+2)%3)
            );

        } else {
            geo_debug_assert(
                region_dim(E1.sym.R2) == 1 || region_dim(E2.sym.R2) == 1
            );
            index_t f1 = E1.sym.f2;
            TriangleRegion R1 = E1.sym.R2;
            index_t f2 = E2.sym.f2;
            TriangleRegion R2 = E2.sym.R2;
            if(region_dim(R1) == 1) {
                std::swap(f1,f2);
                std::swap(R1,R2);
            }

            index_t e = index_t(R2) - index_t(T2_RGN_E0);
            geo_debug_assert(e < 3);

            I = plane_line_intersection(
                mesh_facet_vertex(f1,0),
                mesh_facet_vertex(f1,1),
                mesh_facet_vertex(f1,2),
                mesh_facet_vertex(f2,(e+1)%3),
                mesh_facet_vertex(f2,(e+2)%3)
            );
        }
    }

    void MeshInTriangle::save(const std::string& filename) const {
        Mesh M;
        M.vertices.set_dimension(2);
        for(index_t v=0; v<CDTBase2d::nv(); ++v) {
            vec2 p = vertex_[v].get_UV_approx();
            M.vertices.create_vertex(p.data());
        }
        for(index_t t=0; t<CDTBase2d::nT(); ++t) {
            M.facets.create_triangle(
                CDTBase2d::Tv(t,0),
                CDTBase2d::Tv(t,1),
                CDTBase2d::Tv(t,2)
            );
        }

        Attribute<double> tex_coord;
        tex_coord.create_vector_attribute(
            M.facet_corners.attributes(), "tex_coord", 2
        );
        static double triangle_tex[3][2] = {
            {0.0, 0.0},
            {1.0, 0.0},
            {0.0, 1.0}
        };
        for(index_t c: M.facet_corners) {
            tex_coord[2*c]   = triangle_tex[c%3][0];
            tex_coord[2*c+1] = triangle_tex[c%3][1];
        }
        mesh_save(M, filename);
    }

    /**************************************************************************/

    CoplanarFacets::CoplanarFacets(
        MeshSurfaceIntersection& I, bool clear_attributes,
        double angle_tolerance
    ) :
        I_(I),
        mesh_(I.target_mesh()),
	mesh_copy_(I.readonly_mesh()),
        angle_tolerance_(angle_tolerance),
        facet_group_(I.target_mesh().facets.attributes(),"group"),
        keep_vertex_(I.target_mesh().vertices.attributes(),"keep"),
        c_is_coplanar_(
            I.target_mesh().facet_corners.attributes(),"is_coplanar"
        ),
	f_is_flipped_(I.target_mesh().facets.attributes(),"flipped"),
        halfedges_(*this),
        polylines_(*this)
    {
        if(clear_attributes) {
            for(index_t f: mesh_.facets) {
                facet_group_[f] = NO_INDEX;
            }
            for(index_t v: mesh_.vertices) {
                keep_vertex_[v] = false;
            }
            find_coplanar_facets();
        }
        f_visited_.assign(mesh_.facets.nb(),false);
        h_visited_.assign(mesh_.facet_corners.nb(),false);
        v_visited_.assign(mesh_.vertices.nb(),false);
        v_idx_.assign(mesh_.vertices.nb(),NO_INDEX);
    }

    void CoplanarFacets::find_coplanar_facets() {

	// Positioned by MeshSurfaceIntersection::build_Weiler_model()
        Attribute<bool> corner_is_on_border(
            mesh_.facet_corners.attributes(), "is_on_border"
        );

        for(index_t c: mesh_.facet_corners) {
            c_is_coplanar_[c] = false;
        }

        // TODO: when there is an angle tolerance, one should check instead
        // angle deviation w.r.t. a single seed facet per facet group, because
        // with the present algorithm, if a large number of tiny facets are
        // connected (e.g. highly tessellated cylinder), one may group facets
        // with large angle deviation (without seeing it because each facet has
        // small angle deviation w.r.t. its neighbors).

        parallel_for(
            0, mesh_.facet_corners.nb(),
            [&](index_t c1) {
                index_t f1  = (c1 / 3);
                index_t le1 = (c1 % 3);
                index_t f2 = mesh_.facet_corners.adjacent_facet(c1);

		if(f2 == NO_INDEX) {
		    return;
		}

		// do not traverse true borders
		if(corner_is_on_border[c1]) {
		    return;
		}

		index_t v11 = mesh_.facets.vertex(f1,le1);
		index_t v12 = mesh_.facets.vertex(f1,(le1+1)%3);
		index_t le2 = mesh_.facets.find_edge(f2,v12,v11);
		index_t c2 = mesh_.facets.corner(f2,le2);

#ifdef GEO_DEBUG
		index_t v21 = mesh_.facets.vertex(f2,le2);
		index_t v22 = mesh_.facets.vertex(f2,(le2+1)%3);
		index_t v13 = mesh_.facets.vertex(f1,(le1+2)%3);
		index_t v23 = mesh_.facets.vertex(f2,(le2+2)%3);

		geo_debug_assert(v11 == v22);
		geo_debug_assert(v12 == v21);
		geo_debug_assert(v11!=v12 && v12!=v13 && v13!=v11);
		geo_debug_assert(v21!=v22 && v22!=v23 && v23!=v21);
#endif

		if(c1 > c2) {
		    return;
		}

		// Small optimization: if both triangles come from same
		// original facet then they are coplanar
		if(I_.get_initial_facet(f1) == I_.get_initial_facet(f2)) {
		    c_is_coplanar_[c1] = true;
		    c_is_coplanar_[c2] = true;
		    return;
		}

		// Use original triangles for co-planarity test
		auto [p1, p2, p3] = I_.get_initial_facet_vertices(f1);
		auto [q1, q2, q3] = I_.get_initial_facet_vertices(f2);
		if(triangles_are_coplanar(p1,p2,p3,q1,q2,q3)) {
		    c_is_coplanar_[c1] = true;
		    c_is_coplanar_[c2] = true;
		}
            }
        );
    }

    void CoplanarFacets::get(index_t f, index_t group_id) {

        facets_.resize(0);
        vertices_.resize(0);
        halfedges_.initialize();
        polylines_.initialize();

        // Get facets
        {
            std::stack<index_t> S;
            facet_group_[f] = group_id;
            f_visited_[f] = true;
            S.push(f);
            facets_.push_back(f);
            while(!S.empty()) {
                index_t f1 = S.top();
                S.pop();
                for(index_t le1=0; le1<3; ++le1) {
                    index_t f2 = mesh_.facets.adjacent(f1,le1);
                    if(
                        f2 != NO_INDEX && !f_visited_[f2] &&
                        // 种子限定可能拆分原相邻共面连通域，禁止跨入此前已分配的其他组。
                        (facet_group_[f2]==NO_INDEX || facet_group_[f2]==group_id) &&
                        c_is_coplanar_[mesh_.facets.corner(f1,le1)]
                    ) {
                        // 所有传播面再与本组原种子核对，禁止机器误差沿长邻接链累计成曲面合并。
                        if(I_.get_initial_facet(f2)!=I_.get_initial_facet(f)) {
                            auto [p1,p2,p3]=I_.get_initial_facet_vertices(f);
                            auto [q1,q2,q3]=I_.get_initial_facet_vertices(f2);
                            if(!triangles_are_coplanar(p1,p2,p3,q1,q2,q3)) continue;
                        }
                        facet_group_[f2] = facet_group_[f1];
                        f_visited_[f2] = true;
                        S.push(f2);
                        facets_.push_back(f2);
                    }
                }
            }
            for(index_t cur_f: facets_) {
                f_visited_[cur_f] = false;
            }
        }

        group_id_ = group_id;

	// Initialize projection coordinates, using original facet
	{
	    auto [p1, p2, p3] = I_.get_initial_facet_vertices(facets_[0]);
            coord_index_t projection_axis = PCK::triangle_normal_axis(p1,p2,p3);
            u_ = coord_index_t((projection_axis+1)%3);
            v_ = coord_index_t((projection_axis+2)%3);
	    Sign o = PCK::orient_2d(
		vec2(p1[u_],p1[v_]), vec2(p2[u_],p2[v_]), vec2(p3[u_],p3[v_])
	    );
	    geo_debug_assert(o != ZERO);
            if(o < 0) {
                std::swap(u_,v_);
            }
	}

        // Get vertices and halfedges
        {
            for(index_t f1: facets_) {
                for(index_t le=0; le<3; ++le) {
                    index_t f2 = mesh_.facets.adjacent(f1,le);
                    if(
                        f2 == NO_INDEX ||
                        // 原相邻共面但被种子判据分到另一组的边，也必须成为当前组边界。
                        facet_group_[f2]!=group_id_ ||
                        !c_is_coplanar_[mesh_.facets.corner(f1,le)]
                    ) {
                        halfedges_.add(mesh_.facets.corners_begin(f1)+le);
                        index_t v1 = mesh_.facets.vertex(f1,le);
                        index_t v2 = mesh_.facets.vertex(f1,(le+1)%3);
                        if(!v_visited_[v1]) {
                            v_idx_[v1] = vertices_.size();
                            vertices_.push_back(v1);
                            v_visited_[v1] = true;
                        }
                        if(!v_visited_[v2]) {
                            v_idx_[v2] = vertices_.size();
                            vertices_.push_back(v2);
                            v_visited_[v2] = true;
                        }
                    } else {
			// This one for the particular case of a non-manifold
			// vertex, such as a cone apex touching a facet
			// (ThingiCSG/Basic/cube_cone_1.scad)
			index_t v = mesh_.facets.vertex(f1,le);
			if(keep_vertex_[v] && !v_visited_[v]) {
			    vertices_.push_back(v);
			    v_visited_[v] = true;
			}
		    }
                }
            }
            for(index_t v: vertices_) {
                v_visited_[v] = false;
            }
        }

        // Get polylines
        {
            // Get all polylines starting from vertices with more than
            // 2 incident halfedges.
            for(index_t v: vertices_) {
                if(halfedges_.nb_halfedges_around_vertex(v) > 1) {
                    for(
                        index_t h=halfedges_.vertex_first_halfedge(v);
                        h != NO_INDEX; h = halfedges_.next_around_vertex(h)
                    ) {
                        if(!h_visited_[h]) {
                            polylines_.begin_polyline();
                            index_t h2 = h;
                            do {
                                geo_debug_assert(!h_visited_[h2]);
                                h_visited_[h2] = true;
                                polylines_.add_halfedge(h2);
                                h2 = halfedges_.next_along_polyline(h2);
                            } while(h2 != NO_INDEX && h2 != h);
                            polylines_.end_polyline();
                        }
                    }
                }
            }
            // There can be also closed halfedge loops with no irregular vertex
            for(index_t h: halfedges_) {
                if(!h_visited_[h]) {
                    polylines_.begin_polyline();
                    index_t h2 = h;
                    do {
                        geo_debug_assert(!h_visited_[h2]);
                        h_visited_[h2] = true;
                        polylines_.add_halfedge(h2);
                        h2 = halfedges_.next_along_polyline(h2);
                        geo_debug_assert(h2 != NO_INDEX);
                    } while(h2 != h);
                    polylines_.end_polyline();
                }
            }
            for(index_t h: halfedges_) {
                h_visited_[h] = false;
            }
        }
    }

    void CoplanarFacets::mark_vertices_to_keep() {
        for(index_t P: polylines_) {
            index_t first_v = polylines_.first_vertex(P);
            index_t last_v  = polylines_.last_vertex(P);
            if(first_v != last_v) {
                keep_vertex_[first_v] = true;
                keep_vertex_[last_v]  = true;
            }
            index_t v1 = polylines_.prev_first_vertex(P);
            index_t v2 = NO_INDEX;
            index_t v3 = NO_INDEX;
            for(index_t h: polylines_.halfedges(P)) {
                if(v1 == NO_INDEX) {
                    continue;
                }
                v2 = halfedges_.vertex(h,0);
                v3 = halfedges_.vertex(h,1);
                ExactPoint p1 = I_.exact_vertex(v1);
                ExactPoint p2 = I_.exact_vertex(v2);
                ExactPoint p3 = I_.exact_vertex(v3);
                if(!edges_are_colinear(p1,p2,p3)) {
                    keep_vertex_[v2] = true;
                }
                v1 = v2;
            }
        }
    }

    void CoplanarFacets::save_borders(const std::string& filename) {
        Mesh borders;
        borders.vertices.set_dimension(2);
        index_t cur_idx = 0;
        for(index_t v: vertices_) {
            vec3 p = mesh_.vertices.point(v);
            vec2 q(p[u_],p[v_]);
            borders.vertices.create_vertex(q.data());
            v_idx_[v] = cur_idx;
            ++cur_idx;
        }

        for(index_t h: halfedges_) {
            index_t v1 = halfedges_.vertex(h,0);
            index_t v2 = halfedges_.vertex(h,1);
            v1 = v_idx_[v1];
            v2 = v_idx_[v2];
            geo_debug_assert(v1 != NO_INDEX);
            geo_debug_assert(v2 != NO_INDEX);
            borders.edges.create_edge(v1,v2);
        }

        Attribute<bool> selection(borders.vertices.attributes(), "selection");
        for(index_t v: vertices_) {
            geo_debug_assert(v_idx_[v] != NO_INDEX);
            selection[v_idx_[v]] = keep_vertex_[v];
        }
        mesh_save(borders,filename);
    }

    void CoplanarFacets::save_facet_group(const std::string& filename) {
        Mesh M;
        Attribute<bool> keep_vertex(M.vertices.attributes(),"keep");
        M.vertices.set_dimension(2);
        for(index_t f: facets_) {
            for(index_t lv=0; lv<3; ++lv) {
                index_t v = mesh_.facets.vertex(f,lv);
                v_idx_[v] = NO_INDEX;
            }
        }
        for(index_t f: facets_) {
            for(index_t lv=0; lv<3; ++lv) {
                index_t v = mesh_.facets.vertex(f,lv);
                if(v_idx_[v] == NO_INDEX) {
                    vec3 p = mesh_.vertices.point(v);
                    vec2 q(p[u_], p[v_]);
                    v_idx_[v] = M.vertices.create_vertex(q.data());
                    keep_vertex[v_idx_[v]] = keep_vertex_[v];
                }
            }
            M.facets.create_triangle(
                v_idx_[mesh_.facets.vertex(f,0)],
                v_idx_[mesh_.facets.vertex(f,1)],
                v_idx_[mesh_.facets.vertex(f,2)]
            );
        }

        for(index_t f: facets_) {
            for(index_t lv=0; lv<3; ++lv) {
                index_t v = mesh_.facets.vertex(f,lv);
                v_idx_[v] = NO_INDEX;
            }
        }

        M.facets.connect();
        mesh_save(M,filename);
    }

    void CoplanarFacets::triangulate() {

        // Compute 2D projected BBOX
        double umin =  Numeric::max_float64();
        double vmin =  Numeric::max_float64();
        double umax = -Numeric::max_float64();
        double vmax = -Numeric::max_float64();
        for(index_t f: facets_) {
            for(index_t lv=0; lv<3; ++lv) {
                index_t vx = mesh_.facets.vertex(f,lv);
                double u = mesh_.vertices.point(vx)[u_];
                double v = mesh_.vertices.point(vx)[v_];
                umin = std::min(umin, u);
                umax = std::max(umax, u);
                vmin = std::min(vmin, v);
                vmax = std::max(vmax, v);
            }
        }
        double d = std::max(umax-umin, vmax-vmin);
        d *= 10.0;
        d = std::max(d, 1.0);
        umin-=d; vmin-=d; umax+=d; vmax+=d;

        // Create CDT
        CDT.clear();
        CDT.create_enclosing_rectangle(umin, vmin, umax, vmax);

        for(index_t v: vertices_) {
            if(keep_vertex_[v]) {
                ExactPoint P = I_.exact_vertex(v);
                v_idx_[v] = CDT.insert(exact::vec2h(P[u_], P[v_], P.w), v);
            } else {
                v_idx_[v] = NO_INDEX;
            }
        }

        // Insert constraints
        for(index_t P: polylines_) {
            vector<index_t> Pvertices;
            index_t v = polylines_.first_vertex(P);
            if(keep_vertex_[v]) {
                Pvertices.push_back(v);
            }
            for(index_t h: polylines_.halfedges(P)) {
                v = halfedges_.vertex(h,1);
                if(keep_vertex_[v]) {
                    Pvertices.push_back(v);
                }
            }
            if(
                polylines_.first_vertex(P) == polylines_.last_vertex(P) &&
                Pvertices.size() != 0
            ) {
                Pvertices.push_back(Pvertices[0]);
            }

            for(index_t i=0; i+1<Pvertices.size(); ++i) {
                index_t v1 = v_idx_[Pvertices[i]];
                index_t v2 = v_idx_[Pvertices[i+1]];
                geo_debug_assert(v1 != NO_INDEX);
                geo_debug_assert(v2 != NO_INDEX);
                CDT.insert_constraint(v1,v2,NO_INDEX);
            }
        }

        CDT.remove_external_triangles(true);
    }

// 此方法在Geogram区域三角化阶段提出准确共边补点，最终由内核统一保持相邻面一致。
bool CoplanarFacets::quality_triangulate(
    vector<index_t>& triangles, vector<ExactPoint>& new_points, vector<std::pair<index_t,index_t>>& boundary_edges, bool allow_boundary, index_t point_budget, bool boundary_attempt
) {
#ifndef GEOGRAM_WITH_TRIANGLE
    return false;
#else
    struct Score { index_t bad=0; long double area=0; bool valid=true; };
    auto score = [](const vector<vec3>& points, const vector<int>& cells) {
        Score result;
        for(index_t i=0; i<cells.size(); i+=3) {
            const vec3& a=points[cells[i]];
            const vec3& b=points[cells[i+1]];
            const vec3& c=points[cells[i+2]];
            double area=0.5*length(cross(b-a,c-a));
            if(!std::isfinite(area) || area<=0.0) {result.valid=false; break;}
            double angle=180.0;
            const vec3 corners[3]={a,b,c};
            for(int k=0; k<3; ++k) {
                vec3 x=corners[(k+1)%3]-corners[k];
                vec3 y=corners[(k+2)%3]-corners[k];
                angle=std::min(angle,std::atan2(length(cross(x,y)),dot(x,y))*180.0/3.14159265358979323846);
            }
            if(angle<10.0) {++result.bad; result.area+=area;}
        }
        return result;
    };

    // 只处理确有差面的区域，零差面不调用额外生成器。
    std::map<index_t,int> local;
    vector<index_t> ids;
    vector<double> xy;
    vector<vec3> xyz;
    vector<int> cells;
    for(index_t t=0; t<CDT.nT(); ++t) {
        for(index_t k=0; k<3; ++k) {
            index_t v=CDT.Tv(t,k);
            auto found=local.find(v);
            if(found==local.end()) {
                index_t id=CDT.vertex_id(v);
                if(id==NO_INDEX) return false;
                int index=int(ids.size());
                local[v]=index;
                ids.push_back(id);
                const auto& p=CDT.point(v);
                xy.push_back(p.x.estimate()/p.w.estimate());
                xy.push_back(p.y.estimate()/p.w.estimate());
                xyz.push_back(mesh_.vertices.point(id));
                cells.push_back(index);
            } else {
                cells.push_back(found->second);
            }
        }
    }
    Score before=score(xyz,cells);
    if(!before.valid || before.bad==0 || cells.empty()) return false;

    // 原版准确CDT确定区域和孔洞；Triangle只细化这份已确定的内部三角集合。
    std::set<std::pair<int,int>> boundaries;
    for(index_t t=0; t<CDT.nT(); ++t) {
        for(index_t k=0; k<3; ++k) {
            if(CDT.Tedge_cnstr_first(t,k)!=NO_INDEX) {
                int a=local.at(CDT.Tv(t,(k+1)%3));
                int b=local.at(CDT.Tv(t,(k+2)%3));
                boundaries.insert(std::minmax(a,b));
            }
        }
    }
    vector<int> segments;
    for(auto edge:boundaries) {segments.push_back(edge.first); segments.push_back(edge.second);}
    double orientation=(xy[2*cells[1]]-xy[2*cells[0]])*(xy[2*cells[2]+1]-xy[2*cells[0]+1])-
        (xy[2*cells[1]+1]-xy[2*cells[0]+1])*(xy[2*cells[2]]-xy[2*cells[0]]);
    // 先检查相对于区域尺度的机器精度余量，极短边保留准确CDT，避免浮点补点重合。
    double low[2]={xy[0],xy[1]},high[2]={xy[0],xy[1]},shortest=Numeric::max_float64();
    for(index_t i=0;i<ids.size();++i) for(index_t d=0;d<2;++d) {
        low[d]=std::min(low[d],xy[2*i+d]);high[d]=std::max(high[d],xy[2*i+d]);
    }
    double extent=std::max(high[0]-low[0],high[1]-low[1]);
    for(index_t i=0;i<cells.size();i+=3) for(index_t k=0;k<3;++k) {
        int a=cells[i+k],b=cells[i+(k+1)%3];
        double x=xy[2*a]-xy[2*b],y=xy[2*a+1]-xy[2*b+1];
        shortest=std::min(shortest,std::hypot(x,y));
    }
    double floating_margin=128.0*std::numeric_limits<double>::epsilon()*extent;
    if(shortest<=floating_margin) return false;
    // 双精度投影已失去正面积的区域保留准确CDT，不送入浮点细化器。
    for(index_t i=0; i<cells.size(); i+=3) {
        int a=cells[i],b=cells[i+1],c=cells[i+2];
        double signed_area=(xy[2*b]-xy[2*a])*(xy[2*c+1]-xy[2*a+1])-
            (xy[2*b+1]-xy[2*a+1])*(xy[2*c]-xy[2*a]);
        if(!std::isfinite(signed_area) || signed_area==0.0) return false;
        if(signed_area<0.0) std::swap(cells[i+1],cells[i+2]);
    }
    // 对细长凸四边形直接生成一致二分条带，避免两个区域各自浮点补点造成近重复共边。
    if(allow_boundary && !boundary_attempt && ids.size()==4 && segments.size()==8) {
        vector<vector<int>> adjacent(4);
        for(index_t i=0;i<segments.size();i+=2) {
            adjacent[segments[i]].push_back(segments[i+1]);adjacent[segments[i+1]].push_back(segments[i]);
        }
        bool quad=true;
        for(const auto& neighbors:adjacent) quad=quad && neighbors.size()==2;
        int q[4]={0,0,0,0};
        if(quad) {
            q[1]=adjacent[q[0]][0];
            q[2]=adjacent[q[1]][0]==q[0] ? adjacent[q[1]][1] : adjacent[q[1]][0];
            q[3]=adjacent[q[2]][0]==q[1] ? adjacent[q[2]][1] : adjacent[q[2]][0];
            quad=q[3]!=q[0] && (adjacent[q[3]][0]==q[0] || adjacent[q[3]][1]==q[0]);
        }
        int longest=0;
        if(quad) for(int i=1;i<4;++i) {
            if(length(xyz[q[(i+1)%4]]-xyz[q[i]])>length(xyz[q[(longest+1)%4]]-xyz[q[longest]])) longest=i;
        }
        int ordered[4];for(int i=0;i<4;++i) ordered[i]=q[(longest+i)%4];
        double short_length=std::min(length(xyz[ordered[2]]-xyz[ordered[1]]),length(xyz[ordered[0]]-xyz[ordered[3]]));
        double long_length=std::max(length(xyz[ordered[1]]-xyz[ordered[0]]),length(xyz[ordered[2]]-xyz[ordered[3]]));
        for(int i=0;quad && i<4;++i) {
            vec3 a=xyz[ordered[(i+3)%4]]-xyz[ordered[i]],b=xyz[ordered[(i+1)%4]]-xyz[ordered[i]];
            double corner=std::atan2(length(cross(a,b)),dot(a,b))*180.0/M_PI;
            quad=corner>=20.0;
            int ia=ordered[i],ib=ordered[(i+1)%4],ic=ordered[(i+2)%4];
            double turn=(xy[2*ib]-xy[2*ia])*(xy[2*ic+1]-xy[2*ib+1])-(xy[2*ib+1]-xy[2*ia+1])*(xy[2*ic]-xy[2*ib]);
            int ja=ordered[0],jb=ordered[1],jc=ordered[2];
            double first_turn=(xy[2*jb]-xy[2*ja])*(xy[2*jc+1]-xy[2*jb+1])-(xy[2*jb+1]-xy[2*ja+1])*(xy[2*jc]-xy[2*jb]);
            quad=quad && turn*first_turn>0.0;
        }
        // 两条长边使用二分参数；不同区域请求不同层级时，边点集合仍为包含关系。
        index_t slices=1;
        double needed=short_length>0.0 ? long_length/short_length*std::tan(15.0*M_PI/180.0) : 1e20;
        while(slices<64 && double(slices)<needed) slices*=2;
        quad=quad && needed<=64.0 && long_length>3.0*short_length && slices>1;
        if(quad) {
            vector<ExactPoint> points;
            vector<std::pair<index_t,index_t>> edges;
            vector<vec3> positions=xyz;
            vector<int> strip;
            int previous[2]={ordered[0],ordered[3]};
            for(index_t step=1;step<=slices;++step) {
                int current[2];
                for(int side=0;side<2;++side) {
                    int start=side==0 ? ordered[0] : ordered[3];
                    int end=side==0 ? ordered[1] : ordered[2];
                    if(step==slices) {current[side]=end;continue;}
                    index_t va=ids[start],vb=ids[end];double t=double(step)/double(slices);
                    if(va>vb) {std::swap(va,vb);t=1.0-t;}
                    ExactPoint pa=I_.exact_vertex(va),pb=I_.exact_vertex(vb),p;
                    p.w=pa.w*pb.w;
                    for(coord_index_t d=0;d<3;++d) p[d]=pa[d]*pb.w*(1.0-t)+pb[d]*pa.w*t;
                    Numeric::optimize_number_representation(p);
                    current[side]=int(positions.size());positions.push_back(PCK::approximate(p));
                    points.push_back(p);edges.push_back({va,vb});
                }
                for(int v:{previous[0],current[0],current[1],previous[0],current[1],previous[1]}) strip.push_back(v);
                previous[0]=current[0];previous[1]=current[1];
            }
            Score generated=score(positions,strip);
            if(generated.valid && generated.bad<=before.bad && generated.area<=before.area &&
               (generated.bad<before.bad || generated.area<before.area)) {
                double generated_orientation=(xy[2*ordered[1]]-xy[2*ordered[0]])*(xy[2*ordered[2]+1]-xy[2*ordered[0]+1])-
                    (xy[2*ordered[1]+1]-xy[2*ordered[0]+1])*(xy[2*ordered[2]]-xy[2*ordered[0]]);
                const index_t original_vertices=mesh_.vertices.nb();
                for(index_t i=0;i<strip.size();i+=3) {
                    if(generated_orientation*orientation<0.0) std::swap(strip[i+1],strip[i+2]);
                    for(index_t k=0;k<3;++k) {
                        index_t v=index_t(strip[i+k]);triangles.push_back(v<ids.size() ? ids[v] : original_vertices+v-ids.size());
                    }
                }
                new_points.swap(points);boundary_edges.swap(edges);
                // 条带生成不追加另一日志流，避免并行打印交错污染区域JSON轨迹。
                return true;
            }
        }
    }

    // 每条约束段使用独立标记，返回子段据此归回同一准确原边。
    vector<int> markers(segments.size()/2);
    for(index_t i=0;i<markers.size();++i) markers[i]=int(i)+1;
    triangulateio input{},output{};
    input.pointlist=xy.data(); input.numberofpoints=int(ids.size());
    input.trianglelist=cells.data(); input.numberoftriangles=int(cells.size()/3); input.numberofcorners=3;
    input.segmentlist=segments.data(); input.numberofsegments=int(segments.size()/2); input.segmentmarkerlist=markers.data();
    // 默认只补内部点；仅面积拒绝的改善候选才尝试共边补点，并保留确定上限。
    char options[64];
    std::snprintf(options,sizeof(options),"rpzq20%sS%uQ",boundary_attempt ? "" : "YY",unsigned(point_budget));
    // 仅诊断副本按环境开关保存精确送入Triangle的双精度数组，固定主算法没有该输出。
    static std::atomic<unsigned long> capture_counter(0);
    std::string capture_prefix;
    if(const char* dir=std::getenv("GEO_NATIVE_FAILURE_CAPTURE")) {
        capture_prefix=std::string(dir)+"/triangle_"+std::to_string(capture_counter.fetch_add(1));
        std::ofstream capture(capture_prefix+"_input.json");capture<<std::setprecision(17);
        capture<<"{\"group\":"<<group_id_<<",\"boundary_attempt\":"<<(boundary_attempt ? "true" : "false")
            <<",\"point_budget\":"<<point_budget<<",\"options\":\""<<options<<"\",\"xy\":[";
        for(index_t i=0;i<xy.size();++i) {if(i) capture<<",";capture<<xy[i];}
        capture<<"],\"cells\":[";
        for(index_t i=0;i<cells.size();++i) {if(i) capture<<",";capture<<cells[i];}
        capture<<"],\"segments\":[";
        for(index_t i=0;i<segments.size();++i) {if(i) capture<<",";capture<<segments[i];}
        capture<<"],\"ids\":[";
        for(index_t i=0;i<ids.size();++i) {if(i) capture<<",";capture<<ids[i];}
        capture<<"],\"xyz\":[";
        for(index_t i=0;i<xyz.size();++i) {if(i) capture<<",";capture<<"["<<xyz[i].x<<","<<xyz[i].y<<","<<xyz[i].z<<"]";}
        capture<<"]}";capture.close();
    }
    // Triangle初始化含共享全局常量，串行保护其调用；区域提取仍由Geogram并行执行。
    static std::mutex triangle_mutex;
    {
        std::lock_guard<std::mutex> guard(triangle_mutex);
        ::triangulate(options,&input,&output,nullptr);
    }
    // 完成标记用于区分送入生成器后终止与后续接受判据，不能伪造未返回的数组。
    if(!capture_prefix.empty()) {
        std::ofstream capture(capture_prefix+"_returned.json");capture<<std::setprecision(17);
        capture<<"{\"points\":"<<output.numberofpoints<<",\"triangles\":"<<output.numberoftriangles<<",\"xy\":[";
        for(int i=0;i<2*output.numberofpoints;++i) {if(i) capture<<",";capture<<output.pointlist[i];}
        capture<<"]}";
    }
    auto release=[&]() {
        free(output.pointlist); free(output.pointattributelist); free(output.pointmarkerlist);
        free(output.trianglelist); free(output.triangleattributelist); free(output.trianglearealist);
        free(output.neighborlist); free(output.segmentlist); free(output.segmentmarkerlist);
        free(output.edgelist); free(output.edgemarkerlist); free(output.normlist);
    };
    bool valid=output.numberofpoints>=int(ids.size()) && output.numberofpoints<=int(ids.size())+int(point_budget) &&
        output.numberofcorners==3 && output.numberoftriangles>0;
    for(index_t i=0; valid && i<xy.size(); ++i) valid=(output.pointlist[i]==xy[i]);
    vector<int> on_segment(output.numberofpoints,-1);
    vector<vector<std::pair<int,int>>> chains(markers.size());
    valid=valid && output.segmentmarkerlist!=nullptr;
    for(int i=0;valid && i<output.numberofsegments;++i) {
        int a=output.segmentlist[2*i],b=output.segmentlist[2*i+1],m=output.segmentmarkerlist[i]-1;
        valid=a>=0 && b>=0 && a<output.numberofpoints && b<output.numberofpoints && m>=0 && m<int(chains.size());
        if(!valid) break;
        chains[m].push_back({a,b});
        for(int v:{a,b}) if(v>=int(ids.size())) {
            if(on_segment[v]!=-1 && on_segment[v]!=m) valid=false;
            on_segment[v]=m;
        }
    }
    // 每条原约束必须返回无分叉的完整端点链，不接受额外孔洞边或缺失约束。
    for(index_t m=0;valid && m<chains.size();++m) {
        std::map<int,std::set<int>> neighbors;
        for(auto edge:chains[m]) {neighbors[edge.first].insert(edge.second);neighbors[edge.second].insert(edge.first);}
        int a=segments[2*m],b=segments[2*m+1];
        valid=neighbors[a].size()==1 && neighbors[b].size()==1 && chains[m].size()+1==neighbors.size();
        // GEO容器不接受该单元素初始化列表，显式压入链端点。
        std::set<int> visited;vector<int> stack;stack.push_back(a);
        while(!stack.empty()) {
            int v=stack.back();stack.pop_back();
            if(!visited.insert(v).second) continue;
            valid=valid && neighbors[v].size()==(v==a || v==b ? 1u : 2u);
            for(int q:neighbors[v]) stack.push_back(q);
        }
        valid=valid && visited.size()==neighbors.size();
    }
    bool boundary_unchanged=valid;
    vector<std::pair<index_t,index_t>> proposed_boundaries;

    // 内部点准确提升到支撑平面；边界点用原准确端点插值，端点坐标逐项保持。
    // 使用原输入支撑平面，避免从已经生成的准确点再次构造高阶齐次系数。
    auto [plane_a,plane_b,plane_c]=I_.get_initial_facet_vertices(facets_[0]);
    ExactPoint a(plane_a.x,plane_a.y,plane_a.z,1.0);
    ExactPoint b(plane_b.x,plane_b.y,plane_b.z,1.0);
    ExactPoint c(plane_c.x,plane_c.y,plane_c.z,1.0);
    ExactPoint ab=b-a,ac=c-a;
    exact::vec3 normal(
        ab.y*ac.z-ab.z*ac.y, ab.z*ac.x-ab.x*ac.z, ab.x*ac.y-ab.y*ac.x
    );
    coord_index_t k=coord_index_t(3-u_-v_);
    vector<ExactPoint> proposed;
    for(int i=int(ids.size()); valid && i<output.numberofpoints; ++i) {
        double x=output.pointlist[2*i],y=output.pointlist[2*i+1];
        valid=std::isfinite(x) && std::isfinite(y);
        if(!valid) break;
        ExactPoint p;
        int segment=on_segment[i];
        if(segment>=0) {
            int ia=segments[2*segment],ib=segments[2*segment+1];
            int axis=std::abs(xy[2*ib]-xy[2*ia])>=std::abs(xy[2*ib+1]-xy[2*ia+1]) ? 0 : 1;
            double divisor=xy[2*ib+axis]-xy[2*ia+axis];
            double t=(output.pointlist[2*i+axis]-xy[2*ia+axis])/divisor;
            valid=std::isfinite(t) && t>0.0 && t<1.0;
            if(!valid) break;
            ExactPoint pa=I_.exact_vertex(ids[ia]),pb=I_.exact_vertex(ids[ib]);
            p.w=pa.w*pb.w;
            for(coord_index_t d=0;d<3;++d) p[d]=pa[d]*pb.w+(pb[d]*pa.w-pa[d]*pb.w)*t;
            proposed_boundaries.push_back(std::minmax(ids[ia],ids[ib]));
        } else {
            p.w=normal[k]*a.w;
            p[u_]=x*p.w; p[v_]=y*p.w;
            p[k]=normal.x*a.x+normal.y*a.y+normal.z*a.z-a.w*(normal[u_]*x+normal[v_]*y);
            proposed_boundaries.push_back({NO_INDEX,NO_INDEX});
        }
        Numeric::optimize_number_representation(p);
        vec3 approximate=PCK::approximate(p);
        valid=std::isfinite(approximate.x) && std::isfinite(approximate.y) && std::isfinite(approximate.z);
        proposed.push_back(p);
        xyz.push_back(approximate);
    }
    vector<int> refined;
    if(valid) {
        for(int i=0; i<3*output.numberoftriangles; ++i) {
            int v=output.trianglelist[i];
            if(v<0 || v>=output.numberofpoints) {valid=false; break;}
            refined.push_back(v);
        }
    }
    Score after;
    after.valid=false;
    bool after_score_computed=valid;
    if(valid) after=score(xyz,refined);
    valid=valid && after.valid && after.bad<=before.bad && after.area<=before.area &&
        (after.bad<before.bad || after.area<before.area);
    if(valid) {
        index_t original_vertices=mesh_.vertices.nb();
        for(index_t i=0; i<refined.size(); i+=3) {
            if(orientation<0.0) std::swap(refined[i+1],refined[i+2]);
            for(index_t j=0; j<3; ++j) {
                index_t v=index_t(refined[i+j]);
                triangles.push_back(v<ids.size() ? ids[v] : original_vertices+v-ids.size());
            }
        }
        new_points.swap(proposed);
        boundary_edges.swap(proposed_boundaries);
    }
    // 开发诊断可开启逐区域轨迹，正式计时不启用该环境变量。
    if(std::getenv("GEO_NATIVE_QUALITY_TRACE")!=nullptr) {
        std::lock_guard<std::mutex> guard(triangle_mutex);
        std::cerr << "NATIVE_QUALITY_REGION {\"group\":" << group_id_
                  << ",\"boundary_attempt\":" << (boundary_attempt ? "true" : "false")
                  << ",\"point_budget\":" << point_budget
                  << ",\"source_facets\":" << facets_.size()
                  << ",\"boundary_points\":" << ids.size()
                  << ",\"new_points\":" << output.numberofpoints-int(ids.size())
                  << ",\"boundary_unchanged\":" << (boundary_unchanged ? "true" : "false")
                  << ",\"before_bad\":" << before.bad
                  << ",\"after_score_computed\":" << (after_score_computed ? "true" : "false")
                  << ",\"after_bad\":" << after.bad
                  << ",\"after_valid\":" << (after.valid ? "true" : "false")
                  << ",\"before_bad_area\":" << double(before.area)
                  << ",\"after_bad_area\":" << double(after.area)
                  << ",\"selected\":" << (valid ? "true" : "false") << "}" << std::endl;
    }
    release();
    // 角点至少达到生成目标的四边形，内部点不能改善时才追加一次共边尝试。
    bool regular_quad=(ids.size()==4 && segments.size()==8);
    vector<vector<int>> neighbors(ids.size());
    if(regular_quad) {
        for(index_t i=0;i<segments.size();i+=2) {
            neighbors[segments[i]].push_back(segments[i+1]);neighbors[segments[i+1]].push_back(segments[i]);
        }
        for(index_t i=0;i<ids.size();++i) {
            if(neighbors[i].size()!=2) {regular_quad=false;break;}
            vec3 a=xyz[neighbors[i][0]]-xyz[i],b=xyz[neighbors[i][1]]-xyz[i];
            double angle=std::atan2(length(cross(a,b)),dot(a,b))*180.0/M_PI;
            if(angle<20.0) regular_quad=false;
        }
    }
    // 其余区域只保留第七轮已经证明有用的数量改善、面积拒绝触发，防止全面铺开额外成本。
    if(!valid && allow_boundary && !boundary_attempt && after_score_computed && after.valid && after.bad>0 &&
       (regular_quad || (after.bad<before.bad && after.area>before.area))) {
        return quality_triangulate(triangles,new_points,boundary_edges,true,128,true);
    }
    return valid;
#endif
}


    bool CoplanarFacets::triangles_are_coplanar(
	const vec3& p1, const vec3& p2, const vec3& p3,
	const vec3& q1, const vec3& q2, const vec3& q3
    ) const {
	exact::vec3 N1 = cross(
	    make_vec3<exact::vec3>(p1,p2), make_vec3<exact::vec3>(p1,p3)
	);
	exact::vec3 N2 = cross(
	    make_vec3<exact::vec3>(q1,q2), make_vec3<exact::vec3>(q1,q3)
	);

        if(N1.x.sign() == ZERO && N1.y.sign() == ZERO && N1.z.sign() == ZERO) {
            std::cerr << std::endl;
            std::cerr << "degenerate triangle" << std::endl;
            std::cerr << "aligned: " << PCK::aligned_3d(p1,p2,p3) << std::endl;
            return false;
        }

        if(N2.x.sign() == ZERO && N2.y.sign() == ZERO && N2.z.sign() == ZERO) {
            std::cerr << std::endl;
            std::cerr << "degenerate triangle" << std::endl;
            std::cerr << "aligned: " << PCK::aligned_3d(q1,q2,q3) << std::endl;
            return false;
        }

        // Tolerance for co-planarity test
        if(angle_tolerance_ != 0.0) {
            double threshold = cos(angle_tolerance_ * M_PI / 180.0);
            exact::scalar left = geo_sqr(dot(N1,N2));
            exact::scalar right =
                exact::scalar(threshold*threshold)*length2(N1)*length2(N2);
            return left > right;
        }

        // Exact version
        exact::vec3 N12 = cross(N1,N2);
        if((N12.x.sign()!=ZERO) || (N12.y.sign()!=ZERO) ||(N12.z.sign()!=ZERO)) {
            // 保存坐标造成的机器尺度非共面可单独核对；真实曲率和厚度不依靠角度容差合并。
            vec3 n1(N1.x.estimate(),N1.y.estimate(),N1.z.estimate());
            vec3 n2(N2.x.estimate(),N2.y.estimate(),N2.z.estimate());
            double l1=length(n1),l2=length(n2);
            if(!std::isfinite(l1) || !std::isfinite(l2) || l1==0.0 || l2==0.0) return false;
            n1/=l1;n2/=l2;
            double angle=std::atan2(length(cross(n1,n2)),std::abs(dot(n1,n2)))*180.0/M_PI;
            if(angle>1e-5) return false;
            const vec3 points[6]={p1,p2,p3,q1,q2,q3};
            double scale=0.0,residual=0.0;
            for(const vec3& p:points) {
                for(coord_index_t d=0;d<3;++d) scale=std::max(scale,std::abs(p[d]));
                scale=std::max(scale,length(p-p1));
                residual=std::max(residual,std::abs(dot(p-p1,n1)));
                residual=std::max(residual,std::abs(dot(p-q1,n2)));
            }
            if(residual>128.0*std::numeric_limits<double>::epsilon()*scale) return false;
            // 非准确共面只允许原相邻三角形组成凸四边形，禁止扩展为一般曲面组。
            const vec3 left[3]={p1,p2,p3},right[3]={q1,q2,q3};
            int shared_left[2],shared_count=0,opposite_left=-1,opposite_right=-1;
            for(int i=0;i<3;++i) {
                bool common=false;
                for(int j=0;j<3;++j) common=common || (left[i].x==right[j].x && left[i].y==right[j].y && left[i].z==right[j].z);
                if(common) {if(shared_count>=2) return false;shared_left[shared_count++]=i;} else opposite_left=i;
            }
            for(int j=0;j<3;++j) {
                bool common=false;
                for(int i=0;i<3;++i) common=common || (left[i].x==right[j].x && left[i].y==right[j].y && left[i].z==right[j].z);
                if(!common) {if(opposite_right!=-1) return false;opposite_right=j;}
            }
            if(shared_count!=2 || opposite_left<0 || opposite_right<0) return false;
            vec3 corners[4]={left[shared_left[0]],left[opposite_left],left[shared_left[1]],right[opposite_right]};
            double previous_turn=0.0;
            for(int i=0;i<4;++i) {
                vec3 a=corners[(i+3)%4]-corners[i],b=corners[(i+1)%4]-corners[i];
                if(std::atan2(length(cross(a,b)),dot(a,b))*180.0/M_PI<20.0) return false;
                double turn=dot(cross(b,corners[(i+2)%4]-corners[(i+1)%4]),n1);
                if(turn==0.0 || (i>0 && turn*previous_turn<=0.0)) return false;
                previous_turn=turn;
            }
            return true;
        }

        return true;
    }

    /**************************************************************************/

    bool CoplanarFacets::edges_are_colinear(
        const ExactPoint& P1, const ExactPoint& P2, const ExactPoint& P3
    ) const {

        if(angle_tolerance_ == 0.0) {
            return PCK::on_segment_3d(P2,P1,P3);
        }

        ExactPoint UU = P1-P2;
        exact::vec3 U(UU.x, UU.y, UU.z);
        if(UU.w.sign() == NEGATIVE) {
            U.x.negate(); U.y.negate(); U.z.negate();
        }
        ExactPoint VV = P3-P2;
        exact::vec3 V(VV.x, VV.y, VV.z);
        if(VV.w.sign() == NEGATIVE) {
            V.x.negate(); V.y.negate(); V.z.negate();
        }

        double threshold = cos(angle_tolerance_ * M_PI / 180.0);

        exact::scalar left = dot(U,V);

        if(left.sign() == POSITIVE) {
            return false;
        }

        left = geo_sqr(left);
        exact::scalar right =
            exact::scalar(threshold*threshold)*length2(U)*length2(V);

        return left > right;
    }

    /**************************************************************************/

}
