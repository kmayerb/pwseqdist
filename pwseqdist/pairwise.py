import multiprocessing
import parmap
import itertools
import numpy as np
import scipy

from .metrics import compute_many, compute_many_rect

__all__ = ['apply_pairwise_sq',
           'apply_pairwise_rect']

"""TODO:
These functions are currently not compatible with the numpy subst_metric
because the seqs input woudl be provided as a numpy matric of integers.
I'm not even sure the numpy metric will be faster so not adding now.

Add a numb-compiled version of pairwise_sq and pairwise_rect
  - Convert metrics to code that can be compile with numba
    This would allow the "outer" loop performing pairwise
    distances to also be compiled using numba. The advantage
    is that numba-compiled code can use multithreading to run
    on multiple CPUs, and making use of shared memory.

    I think this could allow for very fast distance calculations"""

def _mati2veci(i, j, n):
    veci = scipy.special.comb(n, 2) - scipy.special.comb(n - i, 2) + (j - i - 1)
    return veci

def apply_pairwise_sq(seqs, metric, ncpus=1, **kwargs):
    """Calculate distance between all pairs of seqs using metric
    and kwargs provided to metric. Will use multiprocessing Pool
    if ncpus > 1.

    For efficiency, will only compute metric on unique values in
    seqs. All values are returned, including redundancies.

    Though written to be used for distance calculations,
    it is general enough that it could be used to run
    any arbitrary function on pairs of elements in seqs.

    Parameters
    ----------
    seqs : list
        List of sequences provided to metric in pairs.
    metric : function
        A distance function of the form
        func(seq1, seq2, **kwargs)
    ncpus : int
        Size of the worker pool to be used by multiprocessing
    **kwargs : keyword arguments
        Additional keyword arguments are supplied to the metric.

    Returns
    -------
    dvec : np.ndarray, length n*(n - 1) / 2
        Vector form of the pairwise distance matrix.
        Use scipy.distance.squareform to convert to a square matrix"""

    useqs = list(set(seqs))
    if len(useqs) == len(seqs):
        useqs = seqs
        translate = False
    else:
        translate = True
        useqs = list(seqs)

    """itertools.combinations creates the i,j pairs in the same order
    as scipy.distance.pdist/squareform"""
    pw_indices = list(itertools.combinations(range(len(useqs)), 2))

    chunk_func = lambda l, n: [l[i:i + n] for i in range(0, len(l), n)]
    chunksz = len(pw_indices) // ncpus
    chunked_indices = chunk_func(pw_indices, chunksz)

    if ncpus > 1:
        with multiprocessing.Pool(ncpus) as pool:
            dists = parmap.map(compute_many,
                               chunked_indices,
                               metric,
                               useqs,
                               **kwargs,
                               pm_parallel=True,
                               pm_pool=pool)
    else:
        dists = parmap.map(compute_many,
                               chunked_indices,
                               metric,
                               useqs,
                               **kwargs,
                               pm_parallel=False)
    
    """Create translation dict from vector_i to mat_ij coordinates for the
    distance matrix of unique seqs (unneccessary, but may be useful later)"""
    # uveci2umati = {veci:(i, j) for veci, (i, j) in enumerate(itertools.combinations(range(len(useqs)), 2))}

    """Get the vector form of the useqs"""
    """n = len(useqs)
    uvec = np.zeros(scipy.special.comb(n, 2))
    for ichunk, dchunk in zip(chunked_indices, dists):
        for (i,j), d in zip(ichunk, dchunk):
            uvec[_mati2veci(i, j, n)] = d"""
    uvec = np.concatenate(dists) # this may be more memory intensive, but should be fine
    
    if translate:
        """Then translate the vector form of the useqs to the vector
        form of the seqs"""
        vout = np.zeros(scipy.special.comb(len(seqs), 2))
        for veci, (i,j), in enumerate(itertools.combinations(range(len(seqs)), 2)):
            ui = useqs.index(seqs[i])
            uj = useqs.index(seqs[j])
            vout[veci] = uvec[_mati2veci(ui, uj, len(useqs))]
    else:
        vout = uvec
    return vout

def apply_pairwise_rect(seqs1, seqs2, metric, ncpus=1, **kwargs):
    """Calculate distance between pairs of sequences in seqs1
    with sequences in seqs2 using metric and kwargs provided to
    metric. Will use multiprocessing Pool if ncpus > 1.

    For efficiency, will only compute metric on unique values in
    seqs1/seqs2. All values are returned, including redundancies.

    Though written to be used for distance calculations,
    it is general enough that it could be used to run
    any arbitrary function on pairs of elements in seqs.

    Parameters
    ----------
    seqs1, seqs2 : lists
        Lists of sequences.
    metric : function
        A distance function of the form
        func(seq1, seq2, **kwargs)
    ncpus : int
        Size of the worker pool to be used by multiprocessing
    **kwargs : keyword arguments
        Additional keyword arguments are supplied to the metric.

    Returns
    -------
    dvec : np.ndarray, length len(seqs1) * len(seqs2)
        Vector form of the pairwise distance rectangle.
    indices : np.ndarray, shape [len(seqs1) * len(seqs2), 2]
        Contains i,j indices on each row where i (j) is an index
        into seqs1 (seqs2) and can be used to recreate a distance rectangle"""

    def _recti2veci(i, j, n2):
        """Translate from rectangle coordinates to vector coordinates"""
        return i * len(n2) + j

    useqs1 = list(set(seqs1))
    if len(useqs1) == len(seqs1):
        useqs1 = seqs1
        translate1 = False
    else:
        translate1 = True
        useqs1 = list(seqs1)

    useqs2 = list(set(seqs2))
    if len(useqs2) == len(seqs2):
        useqs2 = seqs2
        translate2 = False
    else:
        translate2 = True
        useqs2 = list(seqs2)

    pw_indices = list(itertools.product(range(len(useqs1)), range(len(useqs2))))

    chunk_func = lambda l, n: [l[i:i + n] for i in range(0, len(l), n)]
    chunksz = len(pw_indices)//ncpus
    chunked_indices = chunk_func(pw_indices, chunksz)

    if ncpus > 1:
        with multiprocessing.Pool(ncpus) as pool:
            dists = parmap.map(compute_many_rect,
                               chunked_indices,
                               metric,
                               useqs1,
                               useqs2,
                               **kwargs,
                               pm_parallel=True,
                               pm_pool=pool)
    else:
        dists = parmap.map(compute_many_rect,
                               chunked_indices,
                               metric,
                               useqs1,
                               useqs2,
                               **kwargs,
                               pm_parallel=False)
    
    uvec = np.concatenate(dists)
    if translate1 or translate2:
        vec = np.zeros(len(seqs1) * len(seqs2))
        indices = np.zeros((len(seqs1) * len(seqs2), 2))
        for veci, (i, j) in enumerate(itertools.product(range(len(seqs1)), range(seqs2))):
            indices[veci, 0] = i
            indices[veci, 1] = j
            if translate1:
                ui = useqs1.index(seqs1[i])
            else:
                ui = i
            if translate2:
                uj = useqs2.index(seqs2[j])
            else:
                uj = j
            vec[veci] = _recti2veci(ui, uj, len(useqs2))
    else:
        vec = uvec
        indices = np.array(pw_indices)
    return indices, vec