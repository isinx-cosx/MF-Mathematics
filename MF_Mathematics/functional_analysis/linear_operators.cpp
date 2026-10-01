#include "linear_operators.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

#include "fa_internal.h"

namespace mf::functional_analysis {

double operator_norm(const Eigen::MatrixXd& A, const std::string& p) {
    const std::string pl = [&] {
        std::string s;
        for (char ch : p)
            s.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
        return s;
    }();
    if (pl == "inf" || pl == "infty" || pl == "infinity")
        return A.cwiseAbs().rowwise().sum().maxCoeff();  // 最大行和
    if (pl == "fro" || pl == "frobenius") return A.norm();  // Frobenius
    if (pl == "2") return detail::spectral_norm(A);         // 谱范数
    if (pl == "1") return A.cwiseAbs().colwise().sum().maxCoeff();  // 最大列和
    throw std::invalid_argument("不支持的范数阶数: " + p);
}

bool is_bounded(const Eigen::MatrixXd& A) {
    return detail::spectral_norm(A) < 1e10;
}

double linear_functional_eval(const std::vector<double>& func,
                              const std::vector<double>& x) {
    if (func.size() != x.size())
        throw std::invalid_argument("维度不匹配: func 与 x 长度不一致");
    double v = 0.0;
    for (std::size_t i = 0; i < func.size(); ++i) v += func[i] * x[i];
    return v;
}

KernelResult kernel_dimension(const Eigen::MatrixXd& A, double tol) {
    const long long m = A.rows();
    const long long n = A.cols();
    const long long rank = detail::matrix_rank(A, tol);

    KernelResult res;
    res.dim_ker = n - rank;
    if (res.dim_ker > 0) {
        Eigen::JacobiSVD<Eigen::MatrixXd> svd(A, Eigen::ComputeFullV);
        for (long long i = rank; i < n; ++i) {
            const Eigen::VectorXd col = svd.matrixV().col(i);
            std::vector<double> basis(col.data(), col.data() + col.size());
            res.kernel_basis.push_back(std::move(basis));
        }
    }
    (void)m;
    return res;
}

}  // namespace mf::functional_analysis
