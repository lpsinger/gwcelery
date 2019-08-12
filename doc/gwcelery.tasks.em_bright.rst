gwcelery.tasks.em_bright module
-------------------------------

This module computes the probabilities that there is a neutron star in
the binary, and that the coalescence event resulted in creation of tidally 
disrupted matter.

The result is returned in the form of a JSON file:

'{"HasNS": 1.0, "HasRemnant": 1.0}'

* ``HasNS``: The probability that at least one of the component masses
             in  the binary is a neutron star. The definition of a
             neutron star in this context simply means an object with 
             mass less than 3.0 solar mass.

* ``HasRemnant``: The probability that the binary system can produce
                  tidally disrupted matter during coalescence. This is
                  computed using the fitting formula in :arxiv:`1807.00011`
                  We are currently using an extremely stiff equation of
                  state (2H) to compute the compactness of the neutron
                  star. This results in a higher chance of labelling
                  a systems with non-zero ``HasRemnant`` value.


.. automodule:: gwcelery.tasks.em_bright

