resource "aws_vpc" "vpc" {
  cidr_block           = var.vpc_cidr_block
  enable_dns_hostnames = true

  tags = {
    Name = var.vpc_name
  }
}

locals {
  # By convention, we start public subnets from the beginning of the CIDR block
  # and private subnets are put into the second half of the block.
  #
  # Example: assuming our default VPC CIDR block of 10.135.0.0/16,
  # these blocks will be:
  #
  # public subnets starting from: 10.135.0.0
  public_subnets_start_cidr = cidrsubnet(var.vpc_cidr_block, 1, 0)
  # private subnets starting from: 10.135.128.0
  private_subnets_start_cidr = cidrsubnet(var.vpc_cidr_block, 1, 1)
}

data "aws_availability_zones" "azs" {
  state = "available"
  # Many of our VPCs run EKS, so we'll exclude AZs not
  # supported by EKS just in case.
  # see https://docs.aws.amazon.com/eks/latest/userguide/network-reqs.html#network-requirements-subnets
  exclude_zone_ids = ["use1-az3", "usw1-az2", "cac1-az3"]
}

resource "aws_subnet" "public_subnets" {
  count = min(length(data.aws_availability_zones.azs.names), var.public_subnet_count)

  vpc_id = aws_vpc.vpc.id

  cidr_block        = cidrsubnet(local.public_subnets_start_cidr, 3, count.index)
  availability_zone = data.aws_availability_zones.azs.names[count.index]

  tags = {
    Name       = "${var.vpc_name}-public-subnet-${data.aws_availability_zones.azs.names[count.index]}"
    visibility = "public"
  }
}

resource "aws_internet_gateway" "vpc_igw" {
  vpc_id = aws_vpc.vpc.id

  tags = {
    Name = "${var.vpc_name}-internet-gw"
  }
}

resource "aws_default_route_table" "vpc_route_table" {
  default_route_table_id = aws_vpc.vpc.default_route_table_id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.vpc_igw.id
  }

  tags = {
    Name = "${var.vpc_name}-route-table"
  }
}

resource "aws_subnet" "private_subnets" {
  count             = min(length(data.aws_availability_zones.azs.names), var.private_subnet_count)
  vpc_id            = aws_vpc.vpc.id
  cidr_block        = cidrsubnet(local.private_subnets_start_cidr, 3, count.index)
  availability_zone = data.aws_availability_zones.azs.names[count.index]

  tags = {
    Name       = "${var.vpc_name}-private-subnet-${data.aws_availability_zones.azs.names[count.index]}"
    visibility = "private"
  }
}

resource "aws_eip" "natgw" {
  count = var.natgw_count

  domain = "vpc"

  tags = {
    Name = "${var.vpc_name}-natgw-eip${count.index}"
  }
}

resource "aws_nat_gateway" "nat" {
  count = var.natgw_count

  allocation_id = element(aws_eip.natgw.*.id, count.index)
  subnet_id     = element(aws_subnet.public_subnets.*.id, count.index)

  tags = {
    Name = "${var.vpc_name}-public-nat${count.index}"
  }
}

resource "aws_route_table" "private" {
  count = length(aws_subnet.private_subnets)

  vpc_id = aws_vpc.vpc.id

  tags = {
    Name = "${var.vpc_name}-private-rt${count.index}"
  }
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private_subnets)
  subnet_id      = element(aws_subnet.private_subnets.*.id, count.index)
  route_table_id = element(aws_route_table.private.*.id, count.index)
}

resource "aws_route" "private" {
  count                  = length(aws_subnet.private_subnets)
  route_table_id         = element(aws_route_table.private.*.id, count.index)
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = element(aws_nat_gateway.nat.*.id, count.index % length(aws_nat_gateway.nat))
}

resource "aws_default_security_group" "default" {
  vpc_id = aws_vpc.vpc.id
}

resource "aws_security_group_rule" "allow_all_outbound_traffic" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "all"
  security_group_id = aws_default_security_group.default.id
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "allow_inbound_traffic_from_itself" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "all"
  security_group_id        = aws_default_security_group.default.id
  source_security_group_id = aws_default_security_group.default.id
}
