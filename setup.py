from setuptools import setup
setup(
    name="OctoPrint-MINT",
    version="1.0.0",
    description="Earn MINT tokens for 3D prints. Direct on-chain via Solana.",
    author="FoundryNet",
    url="https://github.com/FoundryNet/OctoPrint-MINT",
    license="MIT",
    packages=["octoprint_mint"],
    package_data={"octoprint_mint": ["templates/*.jinja2", "static/js/*.js", "static/css/*.css"]},
    include_package_data=True,
    install_requires=["requests>=2.20.0", "solders>=0.21.0", "solana>=0.34.0", "base58>=2.1.0"],
    entry_points={"octoprint.plugin": ["mint = octoprint_mint"]},
    python_requires=">=3.7,<4",
)
