#encoding: utf-8
import sys
sys.path.append('./gen-py/')
import argparse
import time
import csv
import urllib
import os
from thrift import Thrift

from pyutil.thrift.thrift_client import ThriftRetryClient
from base.ttypes import *
from face_predict import FacePredict
from face_predict.ttypes import ImagesPredictReq, ImageInfo, VideoPredictReq


def parse_args():
    p = argparse.ArgumentParser(description='face pre get gender and race and level.')

    p.add_argument('--service_name', default='lab.face_attr.muse.service.maliva.byted.org')
    p.add_argument('--input', type=str, default='in_img.csv')
    p.add_argument('--output', type=str, default='test_output_random.csv')
    p.add_argument('--save_dir', type=str, default='/mnt/cephfs_wj/vc/wangxiyu/data/fk_img_lab/test_random_face/imgs')
    return p.parse_args()


class FacePredictor():
    def __init__(self, service_name=None, servers=None):
        self.client = ThriftRetryClient(FacePredict.Client,
                                        servers=servers, \
                                        consul_name=service_name, \
                                        nonblocking_server=False,
                                        timeout=10, \
                                        conn_timeout=5, max_retries=2)
        self.service_name = service_name

    def predict(self, image_data, b):
        images = [ImageInfo(image_data=x) for x in image_data]

        req = FacePredict.VideoPredictReq(frames=images,
                                          need_level=True,
                                          need_gender=True,
                                          need_race=True,
                                          Base=b)
        try:
            st = time.time()
            resp = self.client.PredictVideo(req)
            print('face predict succes.', time.time() - st, 's')
        except Exception, e:
            print 'predict error', e
            return None
        return resp

def process(url, save_dir):
    this_url = url
    name = url.split('/')[-1]
    file_dir = os.path.join(save_dir, name + '.jpg')
    try:
        if not os.path.exists(file_dir):
            resource = urllib.urlopen(this_url)
            if int(resource.getcode()) == 200:
                output = open(file_dir, "wb")
                output.write(resource.read())
                output.close()
                print "download suss: ", name
            else:
                print "download fail: ", name
                return False
        return True
    except Exception as ex:
        print("error", name, this_url, ex)
        return False


if __name__ == "__main__":
    try:
        b = Base(Caller='lirixi.local')
        args = parse_args()
        service_name = args.service_name

        results = {}
        if os.path.exists(args.output):
            read_file = csv.reader(open(args.output, 'r'))
            for line in read_file:
                results[line[0]] = (line[0], line[1], line[2], line[3], line[4])

        read_file = csv.reader(open(args.input, 'r'))

        save_dir = args.save_dir

        client = FacePredictor(service_name, servers=None)

        i = 0
        for line in read_file:
            i += 1
            print 'id', i
            file_name = line[0].split('/')[-1]

            if file_name not in results.keys() and process(line[0], save_dir):
                images_bin = []
                file_dir = os.path.join(save_dir, file_name + '.jpg')
                with open(file_dir) as f:
                    data = f.read()
                    images_bin.append(data)

                rsp = client.predict(images_bin, b)

                if rsp is not None and len(rsp.predict_results) > 0:
                    level = rsp.predict_results[0].face_level.tag_id
                    gender = rsp.predict_results[0].face_gender.tag_id
                    race = rsp.predict_results[0].face_race.tag_id
                    faces = rsp.BaseResp.Extra['faces']

                    print [file_name, level, gender, race, faces]

                    write_file = csv.writer(open(args.output, 'a'))
                    write_file.writerow([file_name, str(level), str(gender), str(race), str(faces)])
                else:
                    print "load fail: ", file_name
            else:
                print "Already exist: ", file_name

    except Thrift.TException, ex:
        print "%s" % (ex.message)