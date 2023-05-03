import json
import requests
from flask import (
    current_app,
    Blueprint,
    request,
    flash,
    redirect,
    url_for,
    render_template,
)

import pulumi
import pulumi.automation as auto
from pulumi_aws import s3

bp = Blueprint("sites", __name__, url_prefix="/sites")


def create_pulumi_program(content: str):
    # Create a bucket and expose a website index document
    site_bucket = s3.Bucket(
        "s3-website-bucket",
        website=s3.BucketWebsiteArgs(index_document="index.html")
    )
    index_content = content

    # Write index.html into site bucket
    s3.BucketObject(
        "index",
        bucket=site_bucket.id,
        content=index_content,
        key="index.html",
        content_type="text/html; charset=utf-8",
    )

    # Set bucket access policy to read bucket objects
    s3.BucketPolicy(
        "bucket-policy",
        bucket=site_bucket.id,
        policy=site_bucket.id.apply(
            lambda id: json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": {
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        # Policy refers to bucket explicitly
                        "Resource": [f"arn:aws:s3:::{id}/*"],
                    }
                }
            )
        )
    )

    # export the website url
    pulumi.export("webiste_url", site_bucket.website_endpoint)
    pulumi.export("website_content", index_content)


@bp.route("/new", methods=["GET", "POST"])
def create_site():
    """Create new Sites"""
    if request.method == "POST":
        stack_name = request.form.get("site-id")
        file_url = request.form.get("file-url")
        if file_url:
            site_content = requests.get(file_url).text
        else:
            site_content = request.form.get("site-content")

        def pulumi_program():
            return create_pulumi_program(str(site_content))

        try:
            # create a new stack, generating our pulumi program on the fly from the POST body
            stack = auto.create_stack(
                stack_name=str(stack_name),
                project_name=current_app.config["PROJECT_NAME"],
                program=pulumi_program,
            )
            stack.set_config("aws:region", auto.ConfigValue("us-east-1"))
            # deploy the stack, tailing the logs to stdout
            stack.up(on_output=print)
            flash(
                f"Successfully created site '{stack_name}'", category="success")
        except auto.StackAlreadyExistsError:
            flash(
                f"Error: Site with name '{stack_name}' already exists, pick a unique name",
                category="danger",
            )

        return redirect(url_for("sites.list_sites"))

    return render_template("sites/create.html")
