#!/usr/bin/env python3

from aws_cdk import core

from r53rw.r53rw_stack import R53RwStack


app = core.App()
R53RwStack(app, "r53rw")

app.synth()
