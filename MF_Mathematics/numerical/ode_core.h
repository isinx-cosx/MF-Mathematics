#ifndef ODE_CORE_H
#define ODE_CORE_H 

#include <cmath>
#include <string>

inline double euler(double (*f)(double t, double y), double t0, double y0, double t_end, double h){
    int n = std::max(1, static_cast<int>((t_end - t0) / h));
    double h_actual = (t_end - t0) / n;
    double t = t0;
    double y = y0;
    for (int _=0; _<n; _++) {
        y = y + h_actual * f(t, y);
        t = t+ h_actual;
    }
    return y;
}

inline double rk4(double (*f)(double t, double y), double t0, double y0, double t_end, double h){
    int n = std::max(1, static_cast<int>((t_end - t0) / h));
    double h_actual = (t_end - t0)/ n;
    double t = t0;
    double y = y0;
    for (int _=0; _<n; _++){
        double k1 = f(t, y);
        double k2 = f(t + h_actual/2, y + h_actual * k1/2);
        double k3 = f(t + h_actual/2, y + h_actual * k2/2);
        double k4 = f(t + h_actual, y + h_actual * k3);
        y = y + h_actual/6 * (k1 + 2*k2 + 2*k3 + k4);
        t = t + h_actual;
    }
    return y;
}

inline double implicit_euler(double (*f)(double t, double y), double t0, double y0, double t_end, double h){
    int n = std::max(1, static_cast<int>((t_end - t0) / h));
    double h_actual = (t_end - t0)/ n;
    double t = t0;
    double y = y0;
    for (int _=0; _<n; _++){
        double t_next = t + h_actual;
        double y_pred = y + h_actual * f(t, y);
        y = y + h_actual * f(t_next, y_pred);
        t = t_next;
    }
    return y;
}

#endif