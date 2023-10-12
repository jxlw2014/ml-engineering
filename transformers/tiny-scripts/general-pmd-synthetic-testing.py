
"""

This dataset was generated by:

# prep dataset repo
https://huggingface.co/new-dataset => HuggingFaceM4/general-pmd-synthetic-testing
git clone https://huggingface.co/datasets/HuggingFaceM4/general-pmd-synthetic-testing
cd general-pmd-synthetic-testing

# select a few seed records so there is some longer and shorter text, records with images and without, a few variations of each type
rm -rf data
python general-pmd-ds-unpack.py --dataset_name_or_path /hf/m4-master/data/general_pmd/image/localized_narratives__ADE20k/train/00000-00002 --ids 1-10 --target_path data

cd data

# shrink to 32x32 max, keeping ratio
mogrify -format jpg -resize 32x32\> */*jpg

# adjust one record to have no image and no text
cd 1
rm image.jpg text.txt
touch image.null text.null
cd -

cd ..

# create tarball
tar -cvzf data.tar.gz data

# complete the dataset repo
echo "This dataset is designed to be used in testing. It's derived from general-pmd/localized_narratives__ADE20k dataset" >> README.md

# test dataset
cd ..
datasets-cli test general-pmd-synthetic-testing/general-pmd-synthetic-testing.py --all_configs


# push the data
cd general-pmd-synthetic-testing
rm -rf data
git add *
git commit -am "new dataset"
git push

# test
python -c 'from datasets import load_dataset; load_dataset("HuggingFaceM4/general-pmd-synthetic-testing")["100.unique"]'

"""


from PIL import Image, ImageFile
from collections import defaultdict
from datasets import DatasetInfo
from pathlib import Path
from pprint import pprint
import datasets
import itertools
import json
import os

_CITATION = """\
@InProceedings{huggingface:dataset,
title = {Multimodal synthetic dataset for testing / general PMD},
author={HuggingFace, Inc.},
year={2022}
}
"""

_DESCRIPTION = """This dataset is designed to be used in testing. It's derived from general-pmd-10k dataset"""
_HOMEPAGE = "https://huggingface.co/datasets/HuggingFaceM4/general-pmd-synthetic-testing"
_LICENSE = "bigscience-openrail-m"
_URL = "https://huggingface.co/datasets/HuggingFaceM4/general-pmd-synthetic-testing/resolve/main/data.tar.gz"
#_URL = "./data.tar.gz"

sizes = ["100", "300", "1k", "10k"]
types = ["unique", "repeat"]

class GeneralPMDSynthetic(datasets.GeneratorBasedBuilder):

    VERSION = datasets.Version("1.1.1")

    # splits = [f"{s}.{t}" for s in sizes for t in types]
    # BUILDER_CONFIGS = [] # can't use list comprehension and access VERSION due to python scoping design
    # for split in splits:
    #     BUILDER_CONFIGS.append(datasets.BuilderConfig(name=split, version=VERSION, description=f"{split} items split"))
    DEFAULT_CONFIG_NAME = "100.unique"

    def _info(self):
        # script_dir = os.path.abspath(os.path.dirname(__file__))
        # path = os.path.join(script_dir, "dataset_info.json")
        # ds_info = DatasetInfo.from_directory(path)
        # pprint(ds_info)
        # return ds_info

        # XXX: automate
        return datasets.DatasetInfo(
            description=_DESCRIPTION,
            citation=_CITATION,
            homepage=_HOMEPAGE,
            license=_LICENSE,
            features={
                "image":  {"decode": True,    "id": None, "_type": "Image"},
                "text":   {"dtype": "string", "id": None, "_type": "Value"},
                "source": {"dtype": "string", "id": None, "_type": "Value"},
                "meta":   {"dtype": "string", "id": None, "_type": "Value"},
            },
        )

    def _split_generators(self, dl_manager):
        url = _URL
        data_dir = dl_manager.download_and_extract(url)

        return [
            datasets.SplitGenerator(
                name=self.config.name,
                # These kwargs will be passed to _generate_examples
                gen_kwargs={
                    "data_path": os.path.join(data_dir, "data"),
                },
            )
        ]

    def _generate_examples(self, data_path):
        # the split name acts as the designator of how many rows to generate

        size, type = self.config.name.split(".")

        print(f"Generating {size}-long {type} records split")

        # for now handling 100, 10k - can add m
        total_examples = int(size.replace("k", "000"))

        def pack_example(path):
            """ put the directory with and image and text cols into a single datasets record """

            row = {}

            for file in path.glob("*"):
                if file.suffix == ".null":
                    row[file.stem] = None
                elif file.stem == "image":
                    row[file.stem] = Image.open(file)
                elif file.stem in ['meta', 'source', 'text']:
                    row[file.stem] = "".join([l for l in open(file)])
                else:
                    pass # ignore any other files

            return row

        def dump_example_shapes(idx, row):
            """ dump the row stats """
            shapes = {}

            img = row["image"]
            shapes["image"] = 0 if img is None else "x".join(map(str, img.size))

            for col in ['meta', 'source', 'text']:
                item = row[col]
                shapes[col] = 0 if item is None else len(item)

            summary = ", ".join([f"{k}: {v:>9}" for k,v in shapes.items()])
            print(f"rec{idx:>6}: {summary}")

        print()
        rows = [pack_example(subdir) for subdir in sorted(Path(data_path).glob("[0-9]*"))]
        num_rows = len(rows)
        if num_rows == 0:
            raise ValueError(f"can't find any data - check {data_path}")

        print(f"\nStats for {len(rows)} unique records used:")
        for i, row in enumerate(rows): dump_example_shapes(i, row)

        one_none_texts = 0
        def gen_unique_rec(idx, row):
            nonlocal one_none_texts
            """ insert idx as a string at the end of the first non-None entry, or create a new one if all are
            None. The replacement will overwrite the last few characters of the previous string. This ensures
            that each record will be unique """

            uniq_text = str(idx)
            if row["text"] is None:
                # keep one record that has text=None (which is still unique)
                if one_none_texts == 0:
                    one_none_texts = 1
                else:
                    row["text"] = uniq_text
            else:
                row["text"] = row["text"][:-len(uniq_text)] + uniq_text

            return row

        # this being a synthetic dataset we rotate the 1 or more available rows until we generate enough records.
        # in the case of unique type we tweak one text record to be unique
        for i in range(total_examples):
            idx = i % num_rows
            if type == "repeat":
                yield i, rows[idx]
            elif type == "unique":
                yield i, gen_unique_rec(i, rows[idx])