# Non-negative least squares (NNLS) spectral unmixing

## Add NNLS solver

Use `scipy.optimize.nnls` to solve the least-squares problem with non-negativity constraints.

## Update how background is added

Instead of adding a column of 100.0 to the overlap matrix, we can add a column of 2500.0 to the overlap matrix. This will allow us to use the NNLS solver to solve the least-squares problem with non-negativity constraints.

## Update the UI

Add a button to switch between LS and NNLS solvers.

## Comment

It is a separate feature, the user should be able to switch between LS and NNLS solvers.