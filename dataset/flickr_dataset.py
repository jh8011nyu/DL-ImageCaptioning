import os
from collections import defaultdict

import re
import pandas as pd
from PIL import Image
import torch
from torch.utils.data import Dataset
from .enums import UNK_WORD, START_SEQ, END_SEQ, PAD



class Vocabulary:
    """class to convert word to index"""
    def __init__(self):
        # add unk, start_seq, and end_seq to vocab
        self.word2idx = {PAD:0, UNK_WORD: 1, START_SEQ: 2, END_SEQ: 3}
        self.idx2word = {v:k for k,v in self.word2idx.items()}
        self.idx = 4
    
    def add_word(self, word):
        if word not in self.word2idx:
            self.word2idx[word] = self.idx
            self.idx2word[self.idx] = word
            self.idx += 1

    def __call__(self, word):
        if word not in self.word2idx:
            return self.word2idx[UNK_WORD]
        
        return self.word2idx[word]
    
    def __len__(self):
        return len(self.word2idx)

    def encode_seq(self, seq):
        '''
        seq (List[str]): tokenized sentence
        '''
        return [self(word) for word in seq]
    
    def decode_seq(self, seq_idx):
        '''
        seq_idx (List[str]): list of idxes for a tokenized sentence
        '''
        return [self.idx2word[idx] for idx in seq_idx]



class FlickrConvRNN(Dataset):
    def __init__(self, image_dir, image_ids, 
                 label_path, transform=None, 
                 vocab=None, delimiter="|",
                 first_caption_only=False):
        '''
        `image_dir`: dir that stores all images
        `image_ids`: list of image ids from a data split
        `label_path`: path to the result.csv file
        `transform`: torch image transformation
        `vocab`: Vocabulary object to encode captions
        `first_caption_only`: only only first of the five captions
        `delimiter`: delimiter for your label csv file. `|` for flickr30k, `,` for flickr8k
        '''
        self.first_caption_only = first_caption_only
        self.transform = transform
        self.vocab = vocab
        self.image_dir = image_dir
        self.image_ids = image_ids
        
        # get labels that belong to this dataset
        df = pd.read_csv(label_path, delimiter=delimiter)
        df = df[df["image_name"].isin(self.image_ids)]
        records = df.to_dict("record")
        self.labels = defaultdict(list)
        for record in records:
            self.labels[record["image_name"]].append(record[" comment"].strip())

    def __len__(self):
        return len(self.image_ids)
        
    def __getitem__(self, idx):
        '''
        Returns:
            "images" (List[torch.tensor]): list of tensors
            "captions" (List[List[int]]): list of encoded captions
        '''
        # load image
        image_path = os.path.join(self.image_dir, self.image_ids[idx])
        images = [Image.open(image_path).convert("RGB")]
        if self.transform:
            images[0] = self.transform(images[0])
        if not self.first_caption_only:
            # replicate image 5 time for 5 captions
            images = images * 5

        # captions
        captions = self.labels[self.image_ids[idx]]
        encoded_captions = []
        all_captions = []
        for i, caption in enumerate(captions):
            # lowercase, remove special chars
            tokens = caption.split()
            tokens = [re.sub(r'[^a-zA-Z0-9]', '', token.lower()) for token in tokens if token.isalnum()]
            tokens = [token for token in tokens if len(token)] # remove empty token

            # add start_seq and end_seq
            caption = [START_SEQ] + tokens + [END_SEQ]
            
            # encode to indices
           
            if self.first_caption_only and i==0:
                # use only first caption
                 encoded_captions.append(self.vocab.encode_seq(caption))
            all_captions.append(caption)

        
        return {
            "images": images,
            "captions": encoded_captions,
            "all_captions": all_captions
        }


class BatchCollateFn:
    def __call__(self, data):
        '''
        `data`: list of dictionary object each with key: "images", "captions"
            "images" (List[torch.tensor]): list of tensors
            "captions" (List[List[int]]): list of encoded captions
            "all_captions" (List[List[str]]): all 5 captions of a sample
        '''
        images = []
        lengths = [] # actual length of each captions before padding
        captions = []
        all_captions = [] # List[List[List[str]]]
        for batch in data:
            all_captions.append(batch["all_captions"])
            for image in batch["images"]:
                images.append(image.unsqueeze(dim=0)) # after torch.resize shape=(C,H,W) change to (H,W,C)
            for caption in batch["captions"]:
                captions.append(caption)
                lengths.append(len(caption))
        images = torch.vstack(images) # convert to tensor

        # pad each caption
        captions_padded = torch.zeros(len(lengths), max(lengths)).long()
        for i, caption in enumerate(captions):
            length = lengths[i]
            captions_padded[i, :length] = torch.tensor(caption, dtype=torch.long)

        return images, captions_padded, lengths, all_captions
        




