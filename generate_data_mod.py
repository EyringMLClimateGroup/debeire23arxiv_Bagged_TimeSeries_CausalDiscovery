import itertools
import numpy as np
import sys
from collections import defaultdict 
import networkx as nx

def check_stationarity(links):
    """Returns stationarity according to a unit root test

    Assuming a Gaussian Vector autoregressive process

    Three conditions are necessary for stationarity of the VAR(p) model:
    - Absence of mean shifts;
    - The noise vectors are identically distributed;
    - Stability condition on Phi(t-1) coupling matrix (stabmat) of VAR(1)-version  of VAR(p).
    """


    N = len(links)
    # Check parameters
    max_lag = 0

    for j in range(N):
        for link_props in links[j]:
            var, lag = link_props[0]
            # coeff = link_props[1]
            # coupling = link_props[2]

            max_lag = max(max_lag, abs(lag))

    graph = np.zeros((N,N,max_lag))
    couplings = []

    for j in range(N):
        for link_props in links[j]:
            var, lag = link_props[0]
            coeff    = link_props[1]
            coupling = link_props[2]
            if abs(lag) > 0:
                graph[j,var,abs(lag)-1] = coeff
            couplings.append(coupling)

    stabmat = np.zeros((N*max_lag,N*max_lag))
    index = 0

    for i in range(0,N*max_lag,N):
        stabmat[:N,i:i+N] = graph[:,:,index]
        if index < max_lag-1:
            stabmat[i+N:i+2*N,i:i+N] = np.identity(N)
        index += 1

    eig = np.linalg.eig(stabmat)[0]
    # print "----> maxeig = ", np.abs(eig).max()
    if np.all(np.abs(eig) < 1.):
        stationary = True
    else:
        stationary = False

    if len(eig) == 0:
        return stationary, 0.
    else:
        return stationary, np.abs(eig).max()

def generate_nonlinear_VAR(N, T, links, noises, contemp=False):


    if N != len(links) or N != len(noises):
        raise ValueError("links and noises keys must match N.")

    ## List of separable function types
    func_types =  ['linear', 'quadratic', 'cubic', 'inverse', 'log', 'f1', 'f2', 'f3', 'f4', 'nonlinear1']

    noise_types = ['gauss', 'uniform', 'weibull', 'lognormal']

    # Check parameters
    # contemp = False
    max_lag = 0
    for j in range(N):
        noise = noises[j]
        if noise not in noise_types:
            raise ValueError("noise must be in {}.".format(noise_types))

        for link_props in links[j]:
            var, lag = link_props[0]
            # if lag == 0:
            #     contemp = True
            coeff = link_props[1]
            coupling = link_props[2]
            if 'float' not in str(type(coeff)):
                raise ValueError("coeff must be float.")
            if coupling not in func_types:
                raise ValueError("coupling must be in {}.".format(func_types))
            if var not in range(N):
                raise ValueError("var must be in 0..{}.".format(N-1))
            if lag >= 0 or type(lag) != int:
                raise ValueError("lag must be negative int.")

            max_lag = max(max_lag, abs(lag))

    #print("Maximum lag = {}".format(max_lag))

    if contemp and noises[0] != 'gauss':
        raise ValueError("Contemp links only for gaussian noise...")

    def aux_func(xtmp, which):
        funcDict = {
        "linear"    :   xtmp,
        "quadratic" :   xtmp**2,
        "cubic"     :   xtmp**3,
        "inverse"   :   1./xtmp,
        "log"       :   np.log(np.abs(xtmp)),
        # "f1"        :   2. * xtmp**2 / (1. + 0.5 * xtmp**4),
        # "f2"        :   xtmp**2,
        "nonlinear1"        :   .2 * (xtmp + 5. * xtmp**2 * np.exp(-xtmp**2 / 20.)),
        "f2"        :   .2 * (xtmp + 5. * xtmp**2 * np.exp(-xtmp**2 / 20.)),
        "f3"        :   .05 * (xtmp + 20. * 1./(np.exp(-2.*(xtmp)) + 1.) * np.exp(-xtmp**2 / 100.)),
        "f4"        :   (1. - 4. * xtmp**3 * np.exp(-xtmp**2 / 2.) ) * xtmp,
        # "f4"        :   (1. - 4. * np.sin(xtmp)* xtmp**3 * np.exp(-xtmp**2 / 2.) ) * xtmp,
        # "f5"        :   (1. - 2 * xtmp**2 * np.exp(-xtmp**2 / 2.)) * xtmp,
        }
        return funcDict[which]

    def func(coeff, x, coupling):
        return coeff * aux_func(x, coupling)

    def inno_noise(T, noise):
        noise_dict = {
        "gauss"     :   np.random.randn(T),
        "weibull"   :   0.225*np.random.weibull(a=0.5, size=T),
        "uniform"   :   1./np.sqrt(1./12.)*(0.5-np.random.rand(T)),
        "lognormal" :   1./np.sqrt((np.exp(1.) - 1.)*np.exp(1.))*np.random.lognormal(size=T),        
        }
        return noise_dict[noise]

    transient = int(.2*T)

    if contemp:
        # print("--> contemp")
        cov = 0.2*np.ones((N, N), dtype = 'float')
        cov[range(N), range(N)] = 1.
        # print(cov)
        X = np.random.multivariate_normal(mean=np.zeros(N), cov=cov, size=T+transient)
    else:
        X = np.zeros((T+transient, N), dtype='float32')
        for j in range(N):
            X[:, j] = inno_noise(T+transient, noises[j])


    for t in range(max_lag, T+transient):
        for j in range(N):
            for link_props in links[j]:
                var, lag = link_props[0]
                if abs(lag) > 0:
                    coeff    = link_props[1]
                    coupling = link_props[2]

                    X[t, j] += func(coeff, X[t+lag, var], coupling)

    X = X[transient:]

    if check_stationarity(links)[0]:
        nonstationary = False
    else:
        nonstationary = True

    return X, nonstationary

class Graph(): 
    def __init__(self,vertices): 
        self.graph = defaultdict(list) 
        self.V = vertices 
  
    def addEdge(self,u,v): 
        self.graph[u].append(v) 
  
    def isCyclicUtil(self, v, visited, recStack): 
  
        # Mark current node as visited and  
        # adds to recursion stack 
        visited[v] = True
        recStack[v] = True
  
        # Recur for all neighbours 
        # if any neighbour is visited and in  
        # recStack then graph is cyclic 
        for neighbour in self.graph[v]: 
            if visited[neighbour] == False: 
                if self.isCyclicUtil(neighbour, visited, recStack) == True: 
                    return True
            elif recStack[neighbour] == True: 
                return True
  
        # The node needs to be poped from  
        # recursion stack before function ends 
        recStack[v] = False
        return False
  
    # Returns true if graph is cyclic else false 
    def isCyclic(self): 
        visited = [False] * self.V 
        recStack = [False] * self.V 
        for node in range(self.V): 
            if visited[node] == False: 
                if self.isCyclicUtil(node,visited,recStack) == True: 
                    return True
        return False
  
    # A recursive function used by topologicalSort 
    def topologicalSortUtil(self,v,visited,stack): 

      # Mark the current node as visited. 
      visited[v] = True

      # Recur for all the vertices adjacent to this vertex 
      for i in self.graph[v]: 
          if visited[i] == False: 
              self.topologicalSortUtil(i,visited,stack) 

      # Push current vertex to stack which stores result 
      stack.insert(0,v) 

    # The function to do Topological Sort. It uses recursive  
    # topologicalSortUtil() 
    def topologicalSort(self): 
        # Mark all the vertices as not visited 
        visited = [False]*self.V 
        stack =[] 

        # Call the recursive helper function to store Topological 
        # Sort starting from all vertices one by one 
        for i in range(self.V): 
          if visited[i] == False: 
              self.topologicalSortUtil(i,visited,stack) 

        return stack

def generate_nonlinear_contemp_timeseries(links, T, noises=None, random_state=None):

    if random_state is None:
        random_state = np.random

    # links must be {j:[((i, -tau), func), ...], ...}
    # coeff is coefficient
    # func is a function f(x) that becomes linear ~x in limit
    # noises is a random_state.___ function
    N = len(links.keys())
    if noises is None:
        noises = [random_state.randn for j in range(N)]

    if N != max(links.keys())+1 or N != len(noises):
        raise ValueError("links and noises keys must match N.")

    # Check parameters
    max_lag = 0
    contemp = False
    contemp_dag = Graph(N)
    causal_order = list(range(N))
    for j in range(N):
        for link_props in links[j]:
            var, lag = link_props[0]
            coeff = link_props[1]
            func = link_props[2]
            if lag == 0: contemp = True
            if var not in range(N):
                raise ValueError("var must be in 0..{}.".format(N-1))
            if 'float' not in str(type(coeff)):
                raise ValueError("coeff must be float.")
            if lag > 0 or type(lag) != int:
                raise ValueError("lag must be non-positive int.")
            max_lag = max(max_lag, abs(lag))

            # Create contemp DAG
            if var != j and lag == 0:
                contemp_dag.addEdge(var, j)
                # a, b = causal_order.index(var), causal_order.index(j)
                # causal_order[b], causal_order[a] = causal_order[a], causal_order[b]

    if contemp_dag.isCyclic() == 1: 
        raise ValueError("Contemporaneous links must not contain cycle.")

    causal_order = contemp_dag.topologicalSort() 

    transient = int(.2*T)

    X = np.zeros((T+transient, N), dtype='float32')
    for j in range(N):
        X[:, j] = noises[j](T+transient)

    for t in range(max_lag, T+transient):
        for j in causal_order:
            for link_props in links[j]:
                var, lag = link_props[0]
                # if abs(lag) > 0:
                coeff = link_props[1]
                func = link_props[2]

                X[t, j] += coeff * func(X[t + lag, var])

    X = X[transient:]

    if (check_stationarity(links)[0] == False or 
        np.any(np.isnan(X)) or 
        np.any(np.isinf(X)) or
        # np.max(np.abs(X)) > 1.e4 or
        np.any(np.abs(np.triu(np.corrcoef(X, rowvar=0), 1)) > 0.999)):
        nonstationary = True
    else:
        nonstationary = False

    return X, nonstationary


def generate_random_contemp_model(N, L, 
    coupling_coeffs, 
    coupling_funcs, 
    auto_coeffs, 
    tau_max, 
    contemp_fraction=0.,
    # num_trials=1000,
    random_state=None):

    def lin(x): return x

    if random_state is None:
        random_state = np.random

    # print links
    a_len = len(auto_coeffs)
    if type(coupling_coeffs) == float:
        coupling_coeffs = [coupling_coeffs]
    c_len  = len(coupling_coeffs)
    func_len = len(coupling_funcs)

    if tau_max == 0:
        contemp_fraction = 1.

    if contemp_fraction > 0.:
        contemp = True
        L_lagged = int((1.-contemp_fraction)*L)
        L_contemp = L - L_lagged
        if L==1: 
            # Randomly assign a lagged or contemp link
            L_lagged = random_state.randint(0,2)
            L_contemp = int(L_lagged == False)

    else:
        contemp = False
        L_lagged = L
        L_contemp = 0


    # for ir in range(num_trials):

    # Random order
    causal_order = list(random_state.permutation(N))

    links = dict([(i, []) for i in range(N)])

    # Generate auto-dependencies at lag 1
    if tau_max > 0:
        for i in causal_order:
            a = auto_coeffs[random_state.randint(0, a_len)]

            if a != 0.:
                links[i].append(((int(i), -1), float(a), lin))

    chosen_links = []
    # Create contemporaneous DAG
    contemp_links = []
    for l in range(L_contemp):

        cause = random_state.choice(causal_order[:-1])
        effect = random_state.choice(causal_order)
        while (causal_order.index(cause) >= causal_order.index(effect)
             or (cause, effect) in chosen_links):
            cause = random_state.choice(causal_order[:-1])
            effect = random_state.choice(causal_order)
        
        contemp_links.append((cause, effect))
        chosen_links.append((cause, effect))

    # Create lagged links (can be cyclic)
    lagged_links = []
    for l in range(L_lagged):

        cause = random_state.choice(causal_order)
        effect = random_state.choice(causal_order)
        while (cause, effect) in chosen_links or cause == effect:
            cause = random_state.choice(causal_order)
            effect = random_state.choice(causal_order)
        
        lagged_links.append((cause, effect))
        chosen_links.append((cause, effect))

    # print(chosen_links)
    # print(contemp_links)
    for (i, j) in chosen_links:

        # Choose lag
        if (i, j) in contemp_links:
            tau = 0
        else:
            tau = int(random_state.randint(1, tau_max+1))
        # print tau
        # CHoose coupling
        c = float(coupling_coeffs[random_state.randint(0, c_len)])
        if c != 0:
            func = coupling_funcs[random_state.randint(0, func_len)]

            links[j].append(((int(i), -tau), c, func))


    # print("No stationary models found in {} trials".format(num_trials))
    return links

def generate_logistic_maps(N, T, links, noise_lev):

    # Check parameters
    # contemp = False
    max_lag = 0
    for j in range(N):
        for link_props in links[j]:
            var, lag = link_props[0]
            max_lag  = max(max_lag, abs(lag))

    transient = int(.2*T)

    # Chaotic logistic map parameter
    r = 4.

    X = np.random.rand(T+transient, N)

    for t in range(max_lag, T+transient):
        for j in range(N):
            added_input = 0.
            for link_props in links[j]:
                var, lag = link_props[0]
                if var != j and abs(lag) > 0:
                    coeff        = link_props[1]
                    coupling     = link_props[2]
                    added_input += coeff*X[t - abs(lag), var]

            X[t, j] = (X[t-1, j] * (r - r*X[t-1, j] - added_input + noise_lev*np.random.rand())) % 1
                        #func(coeff, X[t+lag, var], coupling)

    X = X[transient:]

    if np.any(np.abs(X) == np.inf) or np.any(X == np.nan):
        raise ValueError("Data divergent")
    return X



def generate_random_model(N, L, coupling_coeffs, coupling_types, auto_coeffs, tau_max, num_trials=1000,
                        random_state=None):

    if random_state is None:
        random_state = np.random

    def lin_f(x): return x


    # print links
    a_len = len(auto_coeffs)
    if type(coupling_coeffs) == float:
        coupling_coeffs = [coupling_coeffs]
    c_len  = len(coupling_coeffs)
    ct_len = len(coupling_types)

    for ir in range(num_trials):

        links = dict([(i, []) for i in range(N)])

        # Generate auto-dependencies at lag 1
        for i in range(N):
            a = auto_coeffs[random_state.randint(0, a_len)]

            if a != 0.:
                links[i].append(((int(i), -1), float(a), lin_f))

        # Generate couplings
        all_possible = np.array(list(itertools.permutations(range(N), 2)))
        # Choose L links
        chosen_links = all_possible[random_state.permutation(len(all_possible))[:L]]
        for (i, j) in chosen_links:

            # Choose lag
            tau = int(random_state.randint(1, tau_max+1))
            # print tau
            # CHoose coupling
            c      = float(coupling_coeffs[random_state.randint(0, c_len)])
            c_type = coupling_types[random_state.randint(0, ct_len)]

            links[j].append(((int(i), -tau), c, c_type))
        # print links
        # print check_stationarity(links)[0]
        # print ' '
        # sys.exit(0)

        # Stationarity check assuming model with linear dependencies at least for large x
        if check_stationarity(links)[0]:
            return links

    print("No stationary models found in {} trials".format(num_trials))
    return None


def weighted_avg_and_std(values, axis, weights):
    """Returns the weighted average and standard deviation.

    Parameters
    ---------
    values : array
        Data array of shape (time, variables).

    axis : int
        Axis to average/std about

    weights : array
        Weight array of shape (time, variables).

    Returns
    -------
    (average, std) : tuple of arrays
        Tuple of weighted average and standard deviation along axis.
    """

    values[np.isnan(values)] = 0.
    average  = np.ma.average(values, axis=axis, weights=weights)
    variance = np.sum(weights * (values - np.expand_dims(average, axis)
                                    ) ** 2, axis=axis) / weights.sum(axis=axis)

    return (average, np.sqrt(variance))

def time_bin_with_mask(data, time_bin_length, sample_selector=None):
    """Returns time binned data where only about non-masked values is averaged.

    Parameters
    ----------
    data : array
        Data array of shape (time, variables).

    time_bin_length : int
        Length of time bin.

    mask : bool array, optional (default: None)
        Data mask where True labels masked samples.

    Returns
    -------
    (bindata, T) : tuple of array and int
        Tuple of time-binned data array and new length of array.
    """

    T = len(data)

    time_bin_length = int(time_bin_length)

    if sample_selector is None:
        sample_selector = np.ones(data.shape)

    if np.ndim(data) == 1.:
        data.shape = (T, 1)
        sample_selector.shape = (T, 1)

    bindata = np.zeros(
        (T // time_bin_length,) + data.shape[1:], dtype="float32")
    for index, i in enumerate(range(0, T - time_bin_length + 1,
                                    time_bin_length)):
        # print weighted_avg_and_std(fulldata[i:i+time_bin_length], axis=0,
        # weights=sample_selector[i:i+time_bin_length])[0]
        bindata[index] = weighted_avg_and_std(data[i:i + time_bin_length],
                                              axis=0,
                                              weights=sample_selector[i:i +
                                              time_bin_length])[0]

    T, grid_size = bindata.shape

    return (bindata.squeeze(), T)

def get_latent_links(links, observed_variables, tau_max):

    N = len(links)
    Nobs = len(observed_variables)

    # Construct phi and psi matrices
    phi = np.zeros((tau_max + 1, N, N))
    phi[0] = np.identity(N)

    for j in list(links):
        for par in list(links[j]):
            itau, coeff, coupling_type = par
            i, tau = itau
            phi[abs(tau), j, i] = coeff


    psi = np.zeros((tau_max + 1, N, N))
    psi[0] = np.identity(N)
    for n in range(1, tau_max + 1):
        psi[n] = np.zeros((N, N))
        for s in range(1, n+1):
            psi[n] += np.dot(phi[s], psi[n-s])


    print(psi)
    print(observed_psi)
    # Now check for non-zero entries in psi and construct latent_links
    latent_links = dict([(j, []) for j in range(Nobs)])
    for tauji in zip(*np.where(observed_psi != 0.)):
        tau, j, i = tauji
        if tau > 0:
            latent_links[j].append(((i, -tau), observed_psi[tau,j,i], 'linear'))

    print(latent_links)





if __name__ == '__main__':

    def lin_f(x): return x

    def nonlin_f(x): return (x + 5. * x**2 * np.exp(-x**2 / 20.))

    def weibull(T): return np.random.weibull(a=2, size=T) 

    T = 100
    N = 4
    L = 1*N



    def lin_f(x): return x
    N = 15
    links = generate_random_model(
        N=N, L=N, 
        coupling_coeffs = [-0.4, 0.4], 
        coupling_types=[lin_f], 
        auto_coeffs=[0.2, 0.5, 0.9], 
        tau_max=3, 
        num_trials=1000,
        random_state=None)

    # print (links)

    data, nonstat = generate_nonlinear_contemp_timeseries(links,
     T, noises=[np.random.randn for i in range(N)])

    print (data)
    print(nonstat)
