# Chad visual provenance

This repository uses real meme imagery to ground what `PHILOSOPHY.md` means by **Chad**.

**Yes: these are third-party meme images.** We did not create the underlying cultural artifacts, and we do not claim ownership of them merely because they are displayed here.

The point of showing them is identification, commentary, and explanation of the meme lineage from which “Chad Philosophy” is derived. This page keeps that lineage visible instead of replacing it with a newly generated look-alike.

## Rights boundary

- The images described here are **third-party material**.
- They are **not offered under AlphaClaw's repository license** and this repository does not purport to sublicense them.
- A link, attribution, upload history, or meme's wide circulation is **not the same thing as a copyright license**.
- The repository's purpose in displaying the images is identification and commentary. Whether a particular downstream reuse qualifies as fair use is contextual; this file does not grant anyone a fair-use determination.
- Unless an independent license is established for a particular image, downstream users should treat it as third-party copyrighted material whose rights may be uncertain, anonymous, pseudonymous, or split among contributors.

For the U.S. Copyright Office's explanation of fair use and its four-factor analysis, see:

https://www.copyright.gov/fair-use/more-info.html

## Visual lineage

### Yes Chad / Nordic Gamer

Image used as a visual reference:

https://i.kym-cdn.com/entries/icons/facebook/000/031/015/cover5.jpg

Know Your Meme's entry:

https://knowyourmeme.com/memes/yes-chad

Know Your Meme describes **Yes Chad**, also called **Nordic Gamer**, as a drawn blond man usually captioned “Yes.” Its entry traces the format to Twitter in early August 2019 and identifies an August 1, 2019 post by `@yachs_91` in the early lineage. The entry also places the image inside the wider Nordic / Mediterranean and Wojak meme families.

This repository does not claim that the provenance trail resolves authorship or grants a reusable license to the underlying drawing.

### Virgin vs. Chad

Meme-family entry:

https://knowyourmeme.com/memes/virgin-vs-chad

Know Your Meme traces **Virgin vs. Chad / Virgin Walk** to anonymous 4chan `/r9k/` culture, including a March 2017 “Virgin Walk” illustration and June 2017 comparisons involving Chad and other archetypes.

The meme family is collaborative and derivative by design. That cultural fact is useful provenance; it is not a blanket copyright permission.

### Virgin & Chad illustration

Image:

https://i.kym-cdn.com/photos/images/original/001/323/690/19d.png

Image record:

https://knowyourmeme.com/photos/1323690-virgin-vs-chad

Know Your Meme's image record explicitly notes **“Artwork by Glasses Enthusiast on Tumblr.”** That is the attribution currently preserved here.

### Proper Virgin vs. Chad meme creation

Image:

https://i.kym-cdn.com/photos/images/newsfeed/001/442/467/e37.jpg

Image record:

https://knowyourmeme.com/photos/1442467-virgin-vs-chad

Know Your Meme lists this item as created by **storaket** on December 21, 2018 and labels its source as **Original Content** on the image page. That record is provenance, not a license assertion by this repository.

### “The Chad being the meme”

Image:

https://i.kym-cdn.com/photos/images/newsfeed/001/824/235/fd3.jpg

Image record:

https://knowyourmeme.com/photos/1824235-virgin-vs-chad

Know Your Meme records the upload by **TVBRobotnik** and gives the source as `r/VirginVsChad`. The original creator is not resolved here.

## How the featured image is chosen

The public repository `PaulTiffany/letGPTsustakethewheel` now contains a **Ground Chad** workflow.

It reuses the existing cross-model visual poll mechanics:

1. fetch a small manifest of real Chad-family candidate images;
2. discover concrete image-to-text OpenRouter models whose relevant pricing dimensions are explicitly zero;
3. ask each model to score semantic fit, newcomer clarity, and meme recognizability;
4. preserve every raw model response and parse failure;
5. aggregate the scores without asking the models to decide rights.

The model poll answers only:

> **Which image best grounds this philosophy for someone who does not already know the meme?**

It does **not** answer:

> **Do we own this image?**

> **Is this use legally permitted?**

> **Does attribution create a license?**

Those remain separate questions.

The candidate manifest and poll implementation live here:

- https://github.com/PaulTiffany/letGPTsustakethewheel/blob/main/chad_candidates.json
- https://github.com/PaulTiffany/letGPTsustakethewheel/blob/main/chad_grounding.py
- https://github.com/PaulTiffany/letGPTsustakethewheel/blob/main/.github/workflows/chad-grounding.yml

## The compact version

> “You are displaying somebody else's meme art.”
>
> **Yes.**
>
> “You do not get to pretend that attribution means ownership.”
>
> **Correct.**
>
> “So you keep the provenance, mark the rights boundary, and let readers inspect the lineage?”
>
> **Yes.**
