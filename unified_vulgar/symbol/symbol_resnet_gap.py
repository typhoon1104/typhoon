import mxnet as mx


def residual_unit(data, num_filter, stride, dim_match, name, bottle_neck=True, bn_mom=0.9, workspace=512, memonger=False):
    """Return ResNet Unit symbol for building ResNet
    Parameters
    ----------
    data : str
        Input data
    num_filter : int
        Number of output channels
    bnf : int
        Bottle neck channels factor with regard to num_filter
    stride : tupe
        Stride used in convolution
    dim_match : Boolen
        True means channel number between input and output is the same, otherwise means differ
    name : str
        Base name of the operators
    workspace : int
        Workspace used in convolution operator
    """
    if bottle_neck:
        # the same as https://github.com/facebook/fb.resnet.torch#notes, a bit difference with origin paper
        bn1 = mx.sym.BatchNorm(data=data, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_bn1')
        act1 = mx.sym.Activation(data=bn1, act_type='relu', name=name + '_relu1')
        conv1 = mx.sym.Convolution(data=act1, num_filter=int(num_filter*0.25), kernel=(1,1), stride=(1,1), pad=(0,0),
                                      no_bias=True, workspace=workspace, name=name + '_conv1')
        bn2 = mx.sym.BatchNorm(data=conv1, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_bn2')
        act2 = mx.sym.Activation(data=bn2, act_type='relu', name=name + '_relu2')
        conv2 = mx.sym.Convolution(data=act2, num_filter=int(num_filter*0.25), kernel=(3,3), stride=stride, pad=(1,1),
                                      no_bias=True, workspace=workspace, name=name + '_conv2')
        bn3 = mx.sym.BatchNorm(data=conv2, fix_gamma=False, eps=2e-5, momentum=bn_mom, name=name + '_bn3')
        act3 = mx.sym.Activation(data=bn3, act_type='relu', name=name + '_relu3')
        conv3 = mx.sym.Convolution(data=act3, num_filter=num_filter, kernel=(1,1), stride=(1,1), pad=(0,0), no_bias=True,
                                   workspace=workspace, name=name + '_conv3')
        if dim_match:
            shortcut = data
        else:
            shortcut = mx.sym.Convolution(data=act1, num_filter=num_filter, kernel=(1,1), stride=stride, no_bias=True,
                                            workspace=workspace, name=name+'_sc')
        if memonger:
            shortcut._set_attr(mirror_stage='True')
        return conv3 + shortcut
    else:
        bn1 = mx.sym.BatchNorm(data=data, fix_gamma=False, momentum=bn_mom, eps=2e-5, name=name + '_bn1')
        act1 = mx.sym.Activation(data=bn1, act_type='relu', name=name + '_relu1')
        conv1 = mx.sym.Convolution(data=act1, num_filter=num_filter, kernel=(3,3), stride=stride, pad=(1,1),
                                      no_bias=True, workspace=workspace, name=name + '_conv1')
        bn2 = mx.sym.BatchNorm(data=conv1, fix_gamma=False, momentum=bn_mom, eps=2e-5, name=name + '_bn2')
        act2 = mx.sym.Activation(data=bn2, act_type='relu', name=name + '_relu2')
        conv2 = mx.sym.Convolution(data=act2, num_filter=num_filter, kernel=(3,3), stride=(1,1), pad=(1,1),
                                      no_bias=True, workspace=workspace, name=name + '_conv2')
        if dim_match:
            shortcut = data
        else:
            shortcut = mx.sym.Convolution(data=act1, num_filter=num_filter, kernel=(1,1), stride=stride, no_bias=True,
                                            workspace=workspace, name=name+'_sc')
        if memonger:
            shortcut._set_attr(mirror_stage='True')
        return conv2 + shortcut


def resnet(data, units, num_stage, filter_list, data_type='imagenet', bottle_neck=True, bn_mom=0.9, workspace=512, memonger=False):
    """Return ResNet symbol of cifar10 and imagenet
    Parameters
    ----------
    units : list
        Number of units in each stage
    num_stage : int
        Number of stage
    filter_list : list
        Channel size of each stage
    num_class : int
        Ouput size of symbol
    dataset : str
        Dataset type, only cifar10 and imagenet supports
    workspace : int
        Workspace used in convolution operator
    """
    num_unit = len(units)
    assert(num_unit == num_stage)

    data = mx.sym.BatchNorm(data=data, fix_gamma=True, eps=2e-5, momentum=bn_mom, name='bn_data')
    if data_type == 'cifar10':
        body = mx.sym.Convolution(data=data, num_filter=filter_list[0], kernel=(3, 3), stride=(1,1), pad=(1, 1),
                                  no_bias=True, name="conv0", workspace=workspace)
    elif data_type == 'imagenet':
        body = mx.sym.Convolution(data=data, num_filter=filter_list[0], kernel=(7, 7), stride=(2, 2), pad=(3, 3),
                                  no_bias=True, name="conv0", workspace=workspace)
        body = mx.sym.BatchNorm(data=body, fix_gamma=False, eps=2e-5, momentum=bn_mom, name='bn0')
        body = mx.sym.Activation(data=body, act_type='relu', name='relu0')
        body = mx.symbol.Pooling(data=body, kernel=(3, 3), stride=(2, 2), pad=(1, 1), pool_type='max')
    else:
         raise ValueError("do not support {} yet".format(data_type))

    steps = []

    for i in range(num_stage):
        body = residual_unit(body, filter_list[i+1], (1 if i == 0 else 2, 1 if i == 0 else 2), False,
                             name='stage%d_unit%d' % (i + 1, 1), bottle_neck=bottle_neck, workspace=workspace,
                             memonger=memonger)
        for j in range(units[i]-1):
            body = residual_unit(body, filter_list[i+1], (1,1), True, name='stage%d_unit%d' % (i + 1, j + 2),
                                 bottle_neck=bottle_neck, workspace=workspace, memonger=memonger)

        steps.append(body)

    return steps


def get_symbol_resnet_gap(num_class=2, depth=50, loss_type='softmax', bn_mom=0.9, workspace=512):
    data = mx.sym.Variable(name='data')
    label = mx.sym.Variable(name='softmax')

    if depth == 18:
        units = [2, 2, 2, 2]
    elif depth == 34:
        units = [3, 4, 6, 3]
    elif depth == 50:
        units = [3, 4, 6, 3]
    elif depth == 101:
        units = [3, 4, 23, 3]
    elif depth == 152:
        units = [3, 8, 36, 3]
    elif depth == 200:
        units = [3, 24, 36, 3]
    elif depth == 269:
        units = [3, 30, 48, 8]

    if depth <= 50:
        filter_list = [64, 64, 128, 256, 512]
    else:
        filter_list = [64, 256, 512, 1024, 2048]

    steps = resnet(data, units, 4, filter_list)

    flats = []
    for i, step in enumerate(steps):
        bn1 = mx.sym.BatchNorm(data=step, fix_gamma=False, eps=2e-5, momentum=bn_mom, name='bn1_'+str(i)+'_step')
        relu1 = mx.sym.Activation(data=bn1, act_type='relu', name='relu1_'+str(i)+'_step')
        con1 = mx.sym.Convolution(data=relu1, num_filter=filter_list[-1]/4, kernel=(3, 3), stride=(1, 1), pad=(3, 3),
                                  no_bias=True, name='conv_'+str(i)+'_step', workspace=workspace)

        bn2 = mx.sym.BatchNorm(data=con1, fix_gamma=False, eps=2e-5, momentum=bn_mom, name='bn2_'+str(i)+'_step')
        relu2 = mx.sym.Activation(data=bn2, act_type='relu', name='relu2_'+str(i)+'_step')
        pool = mx.symbol.Pooling(data=relu2, global_pool=True, kernel=(7, 7), pool_type='avg', name='pool_'+str(i)+'_step')
        flat = mx.symbol.Flatten(data=pool)

        flats.append(flat)

    flat = mx.sym.Concat(*flats)
    fc = mx.sym.FullyConnected(data=flat, num_hidden=num_class, name='fc')

    if loss_type == 'softmax':
        pred_loss = mx.symbol.SoftmaxOutput(data=fc, label=label, name='softmax_loss')
    elif loss_type == 'focal':
        pre_softmax = mx.symbol.softmax(fc, name='softmax')

        pre = mx.sym.split(data=pre_softmax, num_outputs=2, axis=1)[1]
        pre = mx.sym.reshape(pre, shape=(-1,))

        loss = focal_loss(pre, label)
        pred_loss = mx.sym.Group([mx.sym.BlockGrad(pre_softmax), loss])
    return pred_loss


def focal_loss(pre, label, gamma=2, alpha=0.25):
    pre = pre + 1e-14
    loss = (alpha * (1 - pre) ** gamma * label * mx.symbol.log(pre) + \
            (1 - alpha) * pre ** gamma * (1 - label) * mx.symbol.log(1 - pre)) * -1
    loss = mx.sym.MakeLoss(mx.symbol.sum(loss), normalization='batch')
    return loss


if __name__ == '__main__':
    net = get_symbol(num_class=2, depth=101, loss_type='softmax', bn_mom=0.9, workspace=512)


