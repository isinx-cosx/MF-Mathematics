#include <Eigen/Dense>
#include <iostream>
int main() {
    Eigen::MatrixXd m(2, 2);
    m << 1, 2, 3, 4;
	std::cout << "Matrix:\n" << m << "\nDeterminant: " << m.determinant() << std::endl;
    return m.determinant() == -2 ? 0 : 1;   // det([[1,2],[3,4]]) = -2
}