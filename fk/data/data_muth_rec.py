#encoding: utf-8
import numpy as np
from mxnet.io import DataIter
from mxnet.io import DataBatch
import mxnet as mx
import random
import cv2
from skimage import transform


class FileIter(DataIter):
    def __init__(self, data_dir,
                 rgb_mean=(0, 0, 0),

                 data_name="data",
                 label_name="softmax",

                 batch_size=2,
                 is_train=1,
                 class_num=2,
                 shape=(3, 224, 224)):

        super(FileIter, self).__init__()
        #  tile or other
        self.mode = 'tile'
        self.is_train = is_train
        self.batch_size = batch_size
        self.mean = np.array(rgb_mean)  # (R, G, B)
        self.shape = shape

        self.data_name = data_name
        self.label_name = label_name

        self.imgrec = mx.recordio.MXIndexedRecordIO(data_dir + ".idx", data_dir + ".rec", 'r')
        self.img_idx = list(self.imgrec.keys)

        self.cursor_batch = -1
        self.num = len(self.img_idx)
        self.class_num = class_num

        self.imgs = np.zeros((self.batch_size, 3, 224, 224))
        self.labels = np.zeros((self.batch_size,))

        self.reset()

        if self.is_train == 1:
            print('train_total', self.num)
        elif self.is_train == 2:
            print('val_total', self.num)
        else:
            print('test_total', self.num)

    @property
    def provide_data(self):
        """The name and shape of data provided by this iterator"""
        return [(self.data_name, (self.batch_size, 3, 224, 224))]

    @property
    def provide_label(self):
        """The name and shape of label provided by this iterator"""
        return [(self.label_name, (self.batch_size, ))]

    def get_batch_size(self):
        return self.batch_size

    def reset(self):
        self.cursor_batch = -1
        random.shuffle(self.img_idx)

    def iter_next(self):
        self.cursor_batch += 1
        if (self.cursor_batch+1) * self.batch_size < self.num + self.getpad():
            return True
        else:
            return False


    def get_data_label(self):
        for i in range(self.batch_size):
            s = self.imgrec.read_idx(self.img_idx[i+self.cursor_batch])
            header, img = mx.recordio.unpack(s)
            img = cv2.imdecode(np.array(bytearray(img)), cv2.IMREAD_COLOR)
            img = self.process(img)
            self.imgs[i] = img
            self.labels[i] = header.label
        data = [mx.nd.array(self.imgs)]
        label = [mx.nd.array(self.labels)]
        return data, label


    def getpad(self):
        if self.num % self.batch_size == 0:
            return 0
        return self.batch_size - self.num % self.batch_size

    def getindex(self):
        return self.cursor_batch

    def process(self, data):
        '''
        预处理
        :param data: (h, w, c)
        :return:
        '''

        shape = self.shape

        if data.shape[0] != data.shape[1]:
            if data.shape[0] > data.shape[1]:
                margin = (data.shape[0] - data.shape[1]) // 2
                data = data[margin:margin + data.shape[1], :]
            else:
                margin = (data.shape[1] - data.shape[0]) // 2
                data = data[:, margin:margin + data.shape[0]]

        if self.is_train == 1:
            data = cv2.resize(data, (shape[2] + 32, shape[1] + 32))
            # 随机裁剪
            h_start = random.randint(0, 31)
            w_start = random.randint(0, 31)

            data = data[h_start:h_start + shape[1], w_start:w_start + shape[2]]
            # 上下镜面
            if random.random() > 0.5:
                data = data[:, ::-1]
            # 左右镜面
            if random.random() > 0.5:
                data = data[:, :, ::-1]

            # 随机旋转
            angle = random.randint(0, 360)
            data = transform.rotate(data, angle)
        else:
            data = cv2.resize(data, (shape[2], shape[1]))

        data = np.array(data, dtype='float32')
        data = cv2.cvtColor(data, cv2.COLOR_BGR2RGB)
        data = np.transpose(data, (2, 0, 1))
        return data

    def next(self):
        if self.iter_next():
            while True:
                data, label = self.get_data_label()
                return DataBatch(data=data, label=label, pad=self.getpad(), index=self.getindex())
        else:
            raise StopIteration
