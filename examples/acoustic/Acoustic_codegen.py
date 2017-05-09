# coding: utf-8
from __future__ import print_function

import numpy as np
from cached_property import cached_property

from devito.interfaces import DenseData, TimeData
from examples.acoustic.fwi_operators import *
from examples.seismic import PointSource, Receiver


class Acoustic_cg(object):
    """
    Class to setup the problem for the Acoustic Wave.

    Note: s_order must always be greater than t_order
    """
    def __init__(self, model, data, source, t_order=2, s_order=2):
        self.model = model
        self.data = data
        self.source = source

        self.t_order = t_order
        self.s_order = s_order

        # Time step can be \sqrt{3}=1.73 bigger with 4th order
        self.dt = self.model.critical_dt
        if self.t_order == 4:
            self.dt *= 1.73

    @cached_property
    def op_fwd(self):
        """Cached operator for forward runs with buffered wavefield"""
        return ForwardOperator(self.model, save=False,
                               data=self.data, source=self.source,
                               time_order=self.t_order,
                               space_order=self.s_order)

    @cached_property
    def op_fwd_save(self):
        """Cached operator for forward runs with unrolled wavefield"""
        return ForwardOperator(self.model, save=True,
                               data=self.data, source=self.source,
                               time_order=self.t_order,
                               space_order=self.s_order)

    @property
    def op_adj(self):
        """Cached operator for adjoint runs"""
        return AdjointOperator(self.model, save=False,
                               data=self.data, source=self.source,
                               time_order=self.t_order,
                               space_order=self.s_order)

    @property
    def op_grad(self):
        """Cached operator for gradient runs"""
        return GradientOperator(self.model, save=False,
                                data=self.data, source=self.source,
                                time_order=self.t_order,
                                space_order=self.s_order)

    @property
    def op_born(self):
        """Cached operator for gradient runs"""
        return BornOperator(self.model, save=False,
                            data=self.data, source=self.source,
                            time_order=self.t_order,
                            space_order=self.s_order)

    def Forward(self, save=False, u_ini=None, **kwargs):
        """
        Forward modelling
        """
        nt, nrec = self.data.shape

        # Create source and receiver symbol
        src = PointSource(name='src', data=self.source.traces,
                          coordinates=self.source.receiver_coords)
        rec = Receiver(name='rec', ntime=nt,
                       coordinates=self.data.receiver_coords)

        # Create the forward wavefield
        u = TimeData(name="u", shape=self.model.shape_domain, time_dim=nt,
                     time_order=2, space_order=self.s_order, save=save,
                     dtype=self.model.dtype)
        if u_ini is not None:
            u.data[0:3, :] = u_ini[:]

        # Execute operator and return wavefield and receiver data
        if save:
            summary = self.op_fwd_save.apply(src=src, rec=rec, u=u, **kwargs)
        else:
            summary = self.op_fwd.apply(src=src, rec=rec, u=u, **kwargs)
        return rec.data, u, summary

    def Adjoint(self, recin, u_ini=None, **kwargs):
        """
        Adjoint modelling
        """
        nt, nrec = self.data.shape

        # Create a new adjoint source and receiver symbol
        srca = PointSource(name='srca', ntime=nt,
                           coordinates=self.source.receiver_coords)
        rec = Receiver(name='rec', data=recin,
                       coordinates=self.data.receiver_coords)

        # Create the forward wavefield
        v = TimeData(name="v", shape=self.model.shape_domain, time_dim=nt,
                     time_order=2, space_order=self.s_order,
                     dtype=self.model.dtype)

        summary = self.op_adj.apply(srca=srca, rec=rec, v=v, **kwargs)
        return srca.data, v, summary

    def Gradient(self, recin, u, **kwargs):
        """
        Gradient operator (adjoint of Linearized Born modelling, action of
        the Jacobian adjoint on an input data)
        """
        nt, nrec = self.data.shape

        # Create receiver symbol
        rec = Receiver(name='rec', data=recin,
                       coordinates=self.data.receiver_coords)

        # Gradient symbol
        grad = DenseData(name="grad", shape=self.model.shape_domain,
                         dtype=self.model.dtype)

        # Create the forward wavefield
        v = TimeData(name="v", shape=self.model.shape_domain, time_dim=nt,
                     time_order=2, space_order=self.s_order,
                     dtype=self.model.dtype)

        summary = self.op_grad.apply(rec=rec, grad=grad, v=v, u=u, **kwargs)
        return grad.data, summary

    def Born(self, dmin, **kwargs):
        """
        Linearized Born modelling
        """
        nt, nrec = self.data.shape

        # Create source and receiver symbols
        src = PointSource(name='src', data=self.source.traces,
                          coordinates=self.source.receiver_coords)
        rec = Receiver(name='rec', ntime=nt,
                       coordinates=self.data.receiver_coords)

        # Create the forward wavefield
        u = TimeData(name="u", shape=self.model.shape_domain, time_dim=nt,
                     time_order=2, space_order=self.s_order,
                     dtype=self.model.dtype)
        U = TimeData(name="U", shape=self.model.shape_domain, time_dim=nt,
                     time_order=2, space_order=self.s_order,
                     dtype=self.model.dtype)
        if isinstance(dmin, np.ndarray):
            dm = DenseData(name="dm", shape=self.model.shape_domain,
                           dtype=self.model.dtype)
            dm.data[:] = self.model.pad(dmin)
        else:
            dm = dmin
        # Execute operator and return wavefield and receiver data
        summary = self.op_born.apply(u=u, U=U, src=src, rec=rec, dm=dm, **kwargs)
        return rec.data, u, U, summary
