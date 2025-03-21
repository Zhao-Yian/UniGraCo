# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
# --------------------------------------------------------
# References:
# ELECTRA https://github.com/google-research/electra
# BEiT: https://github.com/microsoft/unilm/tree/master/beit
# --------------------------------------------------------

from torch.optim.lr_scheduler import _LRScheduler

def param_groups_lrd(model, lr, weight_decay=0.05, no_weight_decay_list=[], layer_decay=.75):
    """
    Parameter groups for layer-wise lr decay
    Following BEiT: https://github.com/microsoft/unilm/blob/master/beit/optim_factory.py#L58
    """
    param_group_names = {}
    param_groups = {}
    num_layers = len(model.backbone.blocks) + 1
    layer_scales = list(layer_decay ** (num_layers - i) for i in range(num_layers + 1))
    for n, p in model.backbone.named_parameters():
        if not p.requires_grad:
            continue

        # no decay: all 1D parameters and model specific ones
        if p.ndim == 1 or n in no_weight_decay_list:
            g_decay = "no_decay"
            this_decay = 0.
        else:
            g_decay = "decay"
            this_decay = weight_decay
            
        layer_id = get_layer_id_for_vit(n, num_layers)
        group_name = "layer_%d_%s" % (layer_id, g_decay)

        if group_name not in param_group_names:
            this_scale = layer_scales[layer_id]

            param_group_names[group_name] = {
                "lr_scale": this_scale,
                "lr": lr * this_scale,
                "weight_decay": this_decay,
                "params": [],
            }
            param_groups[group_name] = {
                "lr_scale": this_scale,
                "lr": lr * this_scale,
                "weight_decay": this_decay,
                "params": [],
            }

        param_group_names[group_name]["params"].append(n)
        param_groups[group_name]["params"].append(p)

    params = list(param_groups.values())

    for n, p in model.neck.named_parameters():
        if not p.requires_grad:
            continue
        params.append({"params": p, "weight_decay": weight_decay})

    for n, p in model.head.named_parameters():
        if not p.requires_grad:
            continue
        params.append({"params": p, "weight_decay": weight_decay})

    return params


def get_layer_id_for_vit(name, num_layers):
    """
    Assign a parameter with its layer id
    Following BEiT: https://github.com/microsoft/unilm/blob/master/beit/optim_factory.py#L33
    """
    if name in ['cls_token', 'pos_embed']:
        return 0
    elif name.startswith('patch_embed'):
        return 0
    elif name.startswith('blocks'):
        return int(name.split('.')[1]) + 1
    else:
        return num_layers

class CustomMultiStepLR(_LRScheduler):
    def __init__(self, optimizer, milestones, gammas, last_epoch=-1):
        self.milestones = milestones
        self.gammas = gammas
        assert len(self.milestones) == len(self.gammas), "milestones and gammas must have the same length"
        super(CustomMultiStepLR, self).__init__(optimizer, last_epoch)

    def get_lr(self):
        if self.last_epoch in self.milestones:
            index = self.milestones.index(self.last_epoch)
            return [base_lr * self.gammas[index] for base_lr in self.base_lrs]
        return self.base_lrs

    def step(self, epoch=None):
        # 调用父类的step方法更新学习率
        super(CustomMultiStepLR, self).step(epoch)
        # 打印当前epoch和学习率
        if epoch is None:
            epoch = self.last_epoch + 1
        lrs = self.get_lr()
        print(f"Epoch {epoch}: Setting learning rate to {lrs[0]}")